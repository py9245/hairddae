package com.example.beapp.api;

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
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.security.AuthCookieManager;
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

    @Test
    void protectedEndpointRequiresJwt() throws Exception {
        mockMvc.perform(get("/api/me"))
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
                .andExpect(jsonPath("$.userID").value("TestUser01"));
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

        mockMvc.perform(get("/api/me")
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

        mockMvc.perform(get("/api/me")
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
    void signupValidationReturnsCommonErrorShape() throws Exception {
        mockMvc.perform(post("/api/accounts/signin")
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
        mockMvc.perform(post("/api/accounts/signin")
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
    void signupReturnsDuplicateIdMessageWithoutSeparateCheckApi() throws Exception {
        mockMvc.perform(post("/api/accounts/signin")
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
    void hairApplyStartCreatesTrackableJob() throws Exception {
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

        MvcResult applyStartResult = mockMvc.perform(post("/api/home/hairapplystart")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(accessTokenCookie)
                        .content("""
                                {
                                  "hairID": 1
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andReturn();

        JsonNode applyStartBody = objectMapper.readTree(applyStartResult.getResponse().getContentAsString());
        String applySessionId = applyStartBody.get("applySessionId").asText();

        mockMvc.perform(get("/api/home/hairapplystatus/{applySessionId}", applySessionId)
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.applySessionId").value(applySessionId))
                .andExpect(jsonPath("$.jobType").value("HAIR_APPLY"))
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andExpect(jsonPath("$.hairID").value(1));
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
