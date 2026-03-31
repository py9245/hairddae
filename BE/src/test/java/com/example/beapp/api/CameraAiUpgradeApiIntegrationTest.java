package com.example.beapp.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.api.dto.camera.CameraAiUpgradeResponse;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.GoogleIdTokenVerifier;
import com.example.beapp.service.CameraAiUpgradeService;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class CameraAiUpgradeApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CameraAiUpgradeService cameraAiUpgradeService;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @MockBean
    private GoogleIdTokenVerifier googleIdTokenVerifier;

    @Test
    void cameraAiUpgradeRequiresAuthentication() throws Exception {
        MockMultipartFile image = new MockMultipartFile(
                "image",
                "capture.png",
                "image/png",
                "fake-image".getBytes());

        mockMvc.perform(multipart("/api/camera/ai-upgrade")
                        .file(image))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void cameraAiUpgradeAcceptsAuthenticatedMultipartRequest() throws Exception {
        MockCookie accessTokenCookie = login();
        MockMultipartFile image = new MockMultipartFile(
                "image",
                "capture.png",
                "image/png",
                "fake-image".getBytes());

        given(cameraAiUpgradeService.upgrade(anyString(), anyString(), any()))
                .willReturn(CameraAiUpgradeResponse.ok(
                        "request-1234",
                        "/static/camera-ai/request-1234/result.png"));

        mockMvc.perform(multipart("/api/camera/ai-upgrade")
                        .file(image)
                        .param("device_id", "browser-test-device")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.request_id").value("request-1234"))
                .andExpect(jsonPath("$.result_image_url").value("/static/camera-ai/request-1234/result.png"));
    }

    @Test
    void cameraAiUpgradeRejectsMissingImagePart() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(multipart("/api/camera/ai-upgrade")
                        .param("device_id", "browser-test-device")
                        .cookie(accessTokenCookie))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.errors[0].field").value("image"));
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
