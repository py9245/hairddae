package com.example.beapp.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.time.LocalDate;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.entity.UserEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.example.beapp.persistence.repository.HistoryJpaRepository;
import com.example.beapp.persistence.repository.UserJpaRepository;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("history-test")
class HairAppliedHistoryApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserJpaRepository userJpaRepository;

    @Autowired
    private HairJpaRepository hairJpaRepository;

    @Autowired
    private HistoryJpaRepository historyJpaRepository;

    @Autowired
    private org.springframework.security.crypto.password.PasswordEncoder passwordEncoder;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    private Long firstHairId;
    private Long secondHairId;

    @BeforeEach
    void setUp() {
        historyJpaRepository.deleteAll();
        hairJpaRepository.deleteAll();
        userJpaRepository.deleteAll();

        userJpaRepository.save(new UserEntity(
                "HistoryUser01",
                passwordEncoder.encode("P@ssw0rd1"),
                LocalDate.of(2000, 1, 1),
                "M"));

        firstHairId = hairJpaRepository.save(new HairEntity(
                "Short Crop",
                "short",
                "/images/hair-1.png",
                "short crop"))
                .getId();
        secondHairId = hairJpaRepository.save(new HairEntity(
                "Layer Cut",
                "medium",
                "/images/hair-2.png",
                "layer cut"))
                .getId();
    }

    @Test
    void hairClickRequiresAuthenticationAndCameraListEndpointIsRemoved() throws Exception {
        mockMvc.perform(post("/api/home/hairclick")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": 1
                                }
                                """))
                .andExpect(status().isUnauthorized());

        mockMvc.perform(get("/api/hairs/cameralist"))
                .andExpect(status().isNotFound());
    }

    @Test
    void hairClickRecordsAppliedHistoryAndAppliedListReturnsRecentDeduplicatedItems() throws Exception {
        MockCookie accessTokenCookie = login();

        recordHairClick(accessTokenCookie, secondHairId);
        recordHairClick(accessTokenCookie, firstHairId);
        recordHairClick(accessTokenCookie, secondHairId);

        mockMvc.perform(get("/api/mypage/appliedlist")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalCount").value(2))
                .andExpect(jsonPath("$.hairList[0].hairID").value(secondHairId.intValue()))
                .andExpect(jsonPath("$.hairList[1].hairID").value(firstHairId.intValue()));
    }

    private MockCookie login() throws Exception {
        MvcResult loginResult = mockMvc.perform(post("/api/accounts/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "HistoryUser01",
                                  "password": "P@ssw0rd1"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        return extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);
    }

    private void recordHairClick(MockCookie accessTokenCookie, Long hairId) throws Exception {
        mockMvc.perform(post("/api/home/hairclick")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": %d
                                }
                                """.formatted(hairId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.hair_id").value(hairId.intValue()));
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
