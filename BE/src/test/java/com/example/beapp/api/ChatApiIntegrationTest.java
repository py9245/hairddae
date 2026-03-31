package com.example.beapp.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.ChatMessageRepository;
import com.example.beapp.repository.ChatRoomRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.GoogleIdTokenVerifier;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
@TestPropertySource(properties = {
        "app.hair.static-root-path=build/test-chat-static",
        "app.hair.static-base-url=/static",
        "app.chat.storage-dir=chat-test"
})
class ChatApiIntegrationTest {

    private static final String DESIGNER_USER_ID = "ChatDesigner01";
    private static final Path CHAT_STATIC_ROOT = Path.of("build/test-chat-static");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserAccountRepository userAccountRepository;

    @Autowired
    private ChatRoomRepository chatRoomRepository;

    @Autowired
    private ChatMessageRepository chatMessageRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @MockBean
    private GoogleIdTokenVerifier googleIdTokenVerifier;

    @BeforeEach
    void setUp() throws IOException {
        chatRoomRepository.deleteAllByUserId("TestUser01");
        chatRoomRepository.deleteAllByUserId(DESIGNER_USER_ID);
        userAccountRepository.deleteByUserId(DESIGNER_USER_ID);

        Files.createDirectories(CHAT_STATIC_ROOT);
        try (var paths = Files.walk(CHAT_STATIC_ROOT)) {
            paths.sorted(java.util.Comparator.reverseOrder())
                    .filter(path -> !path.equals(CHAT_STATIC_ROOT))
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException ignored) {
                        }
                    });
        }

        userAccountRepository.save(new UserAccount(
                DESIGNER_USER_ID,
                passwordEncoder.encode("P@ssw0rd1"),
                LocalDate.of(1994, 1, 1),
                "F",
                com.example.beapp.model.LoginType.LOCAL,
                null,
                (short) 2));
    }

    @Test
    void createRoomRequiresAuthentication() throws Exception {
        MockMultipartFile appliedImage = new MockMultipartFile(
                "applied_image",
                "applied.png",
                "image/png",
                "png-image".getBytes());

        mockMvc.perform(multipart("/api/chat/rooms")
                        .file(appliedImage)
                        .param("designer_user_id", DESIGNER_USER_ID)
                        .param("hair_id", "5"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void createRoomStoresImageAndReturnsMessages() throws Exception {
        MockCookie accessTokenCookie = login();
        MockMultipartFile appliedImage = new MockMultipartFile(
                "applied_image",
                "applied.png",
                "image/png",
                "png-image".getBytes());

        MvcResult createResult = mockMvc.perform(multipart("/api/chat/rooms")
                        .file(appliedImage)
                        .cookie(accessTokenCookie)
                        .param("designer_user_id", DESIGNER_USER_ID)
                        .param("hair_id", "5")
                        .param("initial_message", "상담 부탁드립니다."))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.room_id").isNumber())
                .andExpect(jsonPath("$.designer_user_id").value(DESIGNER_USER_ID))
                .andExpect(jsonPath("$.initial_image_url").value(org.hamcrest.Matchers.startsWith("/static/chat-test/rooms/")))
                .andReturn();

        JsonNode createResponse = objectMapper.readTree(createResult.getResponse().getContentAsByteArray());
        long roomId = createResponse.path("room_id").asLong();

        mockMvc.perform(get("/api/chat/rooms/{roomId}/messages", roomId)
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.room_id").value(roomId))
                .andExpect(jsonPath("$.messages.length()").value(2))
                .andExpect(jsonPath("$.messages[0].message_type").value("IMAGE"))
                .andExpect(jsonPath("$.messages[0].image_url").value(org.hamcrest.Matchers.startsWith("/static/chat-test/rooms/")))
                .andExpect(jsonPath("$.messages[0].mine").value(true))
                .andExpect(jsonPath("$.messages[1].message_type").value("TEXT"))
                .andExpect(jsonPath("$.messages[1].message_text").value("상담 부탁드립니다."));
    }

    @Test
    void sendMessageSupportsPollingWithAfterIdAndRoomList() throws Exception {
        MockCookie accessTokenCookie = login();
        MockMultipartFile appliedImage = new MockMultipartFile(
                "applied_image",
                "applied.png",
                "image/png",
                "png-image".getBytes());

        MvcResult createResult = mockMvc.perform(multipart("/api/chat/rooms")
                        .file(appliedImage)
                        .cookie(accessTokenCookie)
                        .param("designer_user_id", DESIGNER_USER_ID)
                        .param("hair_id", "5"))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode createResponse = objectMapper.readTree(createResult.getResponse().getContentAsByteArray());
        long roomId = createResponse.path("room_id").asLong();

        MvcResult initialMessagesResult = mockMvc.perform(get("/api/chat/rooms/{roomId}/messages", roomId)
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.messages.length()").value(1))
                .andReturn();

        JsonNode initialMessages = objectMapper.readTree(initialMessagesResult.getResponse().getContentAsByteArray());
        long initialMessageId = initialMessages.path("messages").get(0).path("id").asLong();

        mockMvc.perform(post("/api/chat/rooms/{roomId}/messages", roomId)
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "message_text": "추가 상담 가능할까요?"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.room_id").value(roomId))
                .andExpect(jsonPath("$.message_id").isNumber())
                .andExpect(jsonPath("$.created_at").isNotEmpty());

        mockMvc.perform(get("/api/chat/rooms/{roomId}/messages", roomId)
                        .cookie(accessTokenCookie)
                        .param("after_id", String.valueOf(initialMessageId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.messages.length()").value(1))
                .andExpect(jsonPath("$.messages[0].message_type").value("TEXT"))
                .andExpect(jsonPath("$.messages[0].message_text").value("추가 상담 가능할까요?"));

        mockMvc.perform(get("/api/chat/rooms")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.rooms.length()").value(1))
                .andExpect(jsonPath("$.rooms[0].room_id").value(roomId))
                .andExpect(jsonPath("$.rooms[0].partner_user_id").value(DESIGNER_USER_ID))
                .andExpect(jsonPath("$.rooms[0].last_message_type").value("TEXT"))
                .andExpect(jsonPath("$.rooms[0].last_message_text").value("추가 상담 가능할까요?"));
    }

    private MockCookie login() throws Exception {
        MvcResult loginResult = mockMvc.perform(post("/api/accounts/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "TestUser01",
                                  "password": "P@ssw0rd1"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        return extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);
    }

    private MockCookie extractCookie(MvcResult result, String cookieName) {
        List<String> setCookies = result.getResponse().getHeaders("Set-Cookie");
        String token = setCookies.stream()
                .flatMap(setCookie -> java.util.Arrays.stream(setCookie.split(";")))
                .map(String::trim)
                .filter(part -> part.startsWith(cookieName + "="))
                .map(part -> part.substring((cookieName + "=").length()))
                .findFirst()
                .orElseThrow();
        return new MockCookie(cookieName, token);
    }
}
