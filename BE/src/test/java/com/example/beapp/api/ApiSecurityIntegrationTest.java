package com.example.beapp.api;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;
import java.time.LocalDate;

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

import com.example.beapp.api.dto.hairs.HairMetadataSyncResponse;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class ApiSecurityIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @Test
    void protectedEndpointRequiresJwt() throws Exception {
        mockMvc.perform(get("/api/mypage/user"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void trailingSlashIsAcceptedForMappedEndpoints() throws Exception {
        mockMvc.perform(get("/api/health/"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ok"));

        MvcResult loginResult = mockMvc.perform(post("/api/accounts/login/")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "TestUser01",
                                  "password": "P@ssw0rd1"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        mockMvc.perform(get("/api/mypage/user/")
                        .cookie(extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userID").value("TestUser01"))
                .andExpect(jsonPath("$.birthDate").value("2000-01-01"))
                .andExpect(jsonPath("$.gender").value("M"));
    }

    @Test
    void loginIssuesJwtAndProtectedEndpointAcceptsIt() throws Exception {
        MvcResult loginResult = mockMvc.perform(post("/api/accounts/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "TestUser01",
                                  "password": "P@ssw0rd1"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andReturn();

        mockMvc.perform(get("/api/mypage/user")
                        .cookie(extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userID").value("TestUser01"))
                .andExpect(jsonPath("$.birthDate").value("2000-01-01"))
                .andExpect(jsonPath("$.gender").value("M"));
    }

    @Test
    void logoutBlocksIssuedAccessToken() throws Exception {
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

        MockCookie accessTokenCookie = extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);
        MockCookie refreshTokenCookie = extractCookie(loginResult, AuthCookieManager.REFRESH_TOKEN_COOKIE);

        mockMvc.perform(post("/api/accounts/logout")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(accessTokenCookie)
                        .cookie(refreshTokenCookie)
                        .content("""
                                {
                                  "allDevices": false
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("로그아웃 완료"));

        mockMvc.perform(get("/api/mypage/user")
                        .cookie(accessTokenCookie))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void refreshRotationInvalidatesPreviousRefreshToken() throws Exception {
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

        MvcResult refreshResult = mockMvc.perform(post("/api/accounts/refreshToken")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(extractCookie(loginResult, AuthCookieManager.REFRESH_TOKEN_COOKIE))
                        .content("""
                                {
                                  "rotate": true
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andReturn();

        MockCookie rotatedRefreshToken = extractCookie(refreshResult, AuthCookieManager.REFRESH_TOKEN_COOKIE);

        mockMvc.perform(post("/api/accounts/refreshToken")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(extractCookie(loginResult, AuthCookieManager.REFRESH_TOKEN_COOKIE))
                        .content("""
                                {
                                  "rotate": true
                                }
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));

        mockMvc.perform(post("/api/accounts/refreshToken")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(rotatedRefreshToken)
                        .content("""
                                {
                                  "rotate": false
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    void refreshAllowsInvalidAccessCookieWhenRefreshTokenIsValid() throws Exception {
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

        MockCookie invalidAccessTokenCookie = new MockCookie(
                AuthCookieManager.ACCESS_TOKEN_COOKIE,
                "invalid.access.token");

        mockMvc.perform(post("/api/accounts/refreshToken")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(invalidAccessTokenCookie)
                        .cookie(extractCookie(loginResult, AuthCookieManager.REFRESH_TOKEN_COOKIE))
                        .content("""
                                {
                                  "rotate": true
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));
    }

    @Test
    void signupValidationReturnsCommonErrorShape() throws Exception {
        mockMvc.perform(post("/api/accounts/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "bad",
                                  "password": "short",
                                  "passwordConfirm": "short",
                                  "birthDate": "%s",
                                  "gender": "X"
                                }
                                """.formatted(LocalDate.now().plusDays(1))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.errors").isArray())
                .andExpect(jsonPath("$.errors[0].field").exists());
    }

    @Test
    void signupRejectsPasswordConfirmationMismatch() throws Exception {
        mockMvc.perform(post("/api/accounts/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "NewUser01",
                                  "password": "P@ssw0rd1",
                                  "passwordConfirm": "P@ssw0rd2",
                                  "birthDate": "1998-03-14",
                                  "gender": "F"
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.message").value("비밀번호 확인이 일치하지 않습니다."));
    }

    @Test
    void signupIssuesJwtAndProtectedEndpointAcceptsIt() throws Exception {
        MvcResult signupResult = mockMvc.perform(post("/api/accounts/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "NewUser01",
                                  "password": "P@ssw0rd1",
                                  "passwordConfirm": "P@ssw0rd1",
                                  "birthDate": "1998-03-14",
                                  "gender": "F"
                                }
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.code").value(201))
                .andReturn();

        mockMvc.perform(get("/api/mypage/user")
                        .cookie(extractCookie(signupResult, AuthCookieManager.ACCESS_TOKEN_COOKIE)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userID").value("NewUser01"))
                .andExpect(jsonPath("$.birthDate").value("1998-03-14"))
                .andExpect(jsonPath("$.gender").value("F"));
    }

    @Test
    void signupReturnsDuplicateIdMessageWithoutSeparateCheckApi() throws Exception {
        mockMvc.perform(post("/api/accounts/signup")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "userID": "TestUser01",
                                  "password": "P@ssw0rd1",
                                  "passwordConfirm": "P@ssw0rd1",
                                  "birthDate": "2000-01-01",
                                  "gender": "M"
                                }
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value(409))
                .andExpect(jsonPath("$.message").value("이미 사용 중인 아이디입니다."));
    }

    @Test
    void publicHomeApisExposeNewResponseShape() throws Exception {
        mockMvc.perform(get("/api/home/normalrank"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.best").isArray())
                .andExpect(jsonPath("$.best[0].datasetCode").isString())
                .andExpect(jsonPath("$.latest").isArray())
                .andExpect(jsonPath("$.latest[0].datasetCode").isString());

        mockMvc.perform(get("/api/home/categorylist"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.categoryList").isArray())
                .andExpect(jsonPath("$.categoryList[0].categoryID").exists())
                .andExpect(jsonPath("$.categoryList[0].categoryName").exists());

        mockMvc.perform(get("/api/home/categorycardlist").param("categoryId", "all"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.categoryID").value("all"))
                .andExpect(jsonPath("$.cardList").isArray())
                .andExpect(jsonPath("$.cardList[0].datasetCode").isString());
    }

    @Test
    void authenticatedMypageApisExposeAppliedAndLikeLists() throws Exception {
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

        MockCookie accessTokenCookie = extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);

        mockMvc.perform(get("/api/mypage/appliedlist")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalCount").isNumber())
                .andExpect(jsonPath("$.hairList").isArray())
                .andExpect(jsonPath("$.hairList[0].datasetCode").isString());

        mockMvc.perform(get("/api/mypage/likelist")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.userID").value("TestUser01"))
                .andExpect(jsonPath("$.likeList").isArray())
                .andExpect(jsonPath("$.likeList[0].datasetCode").isString());
    }

    @Test
    void hairApplyBootstrapReturnsInferenceBootstrapPayload() throws Exception {
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

        MockCookie accessTokenCookie = extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);

        mockMvc.perform(post("/api/home/hairapplybootstrap")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(accessTokenCookie)
                        .content("""
                                {
                                  "hair_id": 1,
                                  "device_id": "browser-test-device",
                                  "client_capabilities": {
                                    "feature_schema_version": 2,
                                    "transform_version": "affine_v1"
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.apply_session_id").isString())
                .andExpect(jsonPath("$.feature_schema_version").value(2))
                .andExpect(jsonPath("$.transform_version").value("affine_v1"))
                .andExpect(jsonPath("$.inference.ws_url").isString())
                .andExpect(jsonPath("$.inference.ws_url").value(org.hamcrest.Matchers.containsString("/ws/inference/apply")))
                .andExpect(jsonPath("$.inference.ws_auth_transport").value("sec-websocket-protocol.v1"))
                .andExpect(jsonPath("$.inference.connect_ticket").isString())
                .andExpect(jsonPath("$.inference.node_id").value("infer-gpu-01"))
                .andExpect(jsonPath("$.rtc.enabled").value(true))
                .andExpect(jsonPath("$.rtc.offer_url").value(org.hamcrest.Matchers.containsString("/rtc/inference/offer")))
                .andExpect(jsonPath("$.rtc.connect_ticket").isString());
    }

    @Test
    void hairApplyBootstrapAllowsAnonymousCameraSession() throws Exception {
        mockMvc.perform(post("/api/home/hairapplybootstrap")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": 1,
                                  "device_id": "anon-browser-device",
                                  "client_capabilities": {
                                    "feature_schema_version": 2,
                                    "transform_version": "affine_v1"
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.apply_session_id").isString())
                .andExpect(jsonPath("$.rtc.enabled").value(true))
                .andExpect(jsonPath("$.rtc.connect_ticket").isString());
    }

    @Test
    void hairApplyResumeReusesExistingSessionAndIssuesFreshTicket() throws Exception {
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

        MockCookie accessTokenCookie = extractCookie(loginResult, AuthCookieManager.ACCESS_TOKEN_COOKIE);

        MvcResult bootstrapResult = mockMvc.perform(post("/api/home/hairapplybootstrap")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(accessTokenCookie)
                        .content("""
                                {
                                  "hair_id": 1,
                                  "device_id": "browser-test-device",
                                  "client_capabilities": {
                                    "feature_schema_version": 2,
                                    "transform_version": "affine_v1"
                                  }
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();

        JsonNode bootstrapBody = objectMapper.readTree(bootstrapResult.getResponse().getContentAsString());
        String applySessionId = bootstrapBody.get("apply_session_id").asText();
        String connectTicket = bootstrapBody.get("rtc").get("connect_ticket").asText();

        mockMvc.perform(post("/api/home/hairapplyresume")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(accessTokenCookie)
                        .content("""
                                {
                                  "apply_session_id": "%s",
                                  "device_id": "browser-test-device"
                                }
                                """.formatted(applySessionId)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.apply_session_id").value(applySessionId))
                .andExpect(jsonPath("$.rtc.connect_ticket").isString())
                .andExpect(jsonPath("$.rtc.connect_ticket").value(org.hamcrest.Matchers.not(connectTicket)));
    }

    @Test
    void inferenceHairSyncRequiresSharedSecret() throws Exception {
        MockMultipartFile previewImage = new MockMultipartFile(
                "preview_image",
                "main.png",
                "image/png",
                "fake-image".getBytes());

        mockMvc.perform(multipart("/api/internal/hairs/sync")
                        .file(previewImage)
                        .param("dataset_code", "0003")
                        .param("name", "wolf cut")
                        .param("slug", "wolf-cut")
                        .param("category", "medium")
                        .param("description", "wolf cut metadata"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void inferenceHairSyncUpsertsMetadataWithSharedSecret() throws Exception {
        MockMultipartFile previewImage = new MockMultipartFile(
                "preview_image",
                "main.png",
                "image/png",
                "fake-image".getBytes());

        given(hairMetadataSyncService.upsert(any(), any()))
                .willReturn(HairMetadataSyncResponse.ok(3, "0003", true));

        mockMvc.perform(multipart("/api/internal/hairs/sync")
                        .file(previewImage)
                        .header("X-Inference-Sync-Secret", "test-inference-sync-secret")
                        .param("dataset_code", "0003")
                        .param("name", "wolf cut")
                        .param("slug", "wolf-cut")
                        .param("category", "medium")
                        .param("description", "wolf cut metadata")
                        .param("active", "true"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hair_id").value(3))
                .andExpect(jsonPath("$.dataset_code").value("0003"))
                .andExpect(jsonPath("$.created").value(true));
    }

    @Test
    void inferenceHairSyncMissingRequiredParamReturnsBadRequest() throws Exception {
        MockMultipartFile previewImage = new MockMultipartFile(
                "preview_image",
                "main.png",
                "image/png",
                "fake-image".getBytes());

        mockMvc.perform(multipart("/api/internal/hairs/sync")
                        .file(previewImage)
                        .header("X-Inference-Sync-Secret", "test-inference-sync-secret")
                        .param("dataset_code", "0010")
                        .param("slug", "wolf-cut-0010")
                        .param("category", "medium"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.errors[0].field").value("name"));

        verifyNoInteractions(hairMetadataSyncService);
    }

    @Test
    void inferenceHairSyncBlankRequiredParamReturnsBadRequest() throws Exception {
        MockMultipartFile previewImage = new MockMultipartFile(
                "preview_image",
                "main.png",
                "image/png",
                "fake-image".getBytes());

        mockMvc.perform(multipart("/api/internal/hairs/sync")
                        .file(previewImage)
                        .header("X-Inference-Sync-Secret", "test-inference-sync-secret")
                        .param("dataset_code", "0011")
                        .param("name", "")
                        .param("slug", "wolf-cut-0011")
                        .param("category", "medium"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.errors[0].field").value("name"));

        verifyNoInteractions(hairMetadataSyncService);
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
