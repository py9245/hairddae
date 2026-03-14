package com.example.beapp.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
                .andExpect(header().string("Set-Cookie", org.hamcrest.Matchers.containsString("HttpOnly")))
                .andReturn();

        JsonNode loginBody = objectMapper.readTree(loginResult.getResponse().getContentAsString());
        String accessToken = loginBody.get("accessToken").asText();

        mockMvc.perform(get("/api/me")
                        .header("Authorization", "Bearer " + accessToken))
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

        JsonNode loginBody = objectMapper.readTree(loginResult.getResponse().getContentAsString());
        String accessToken = loginBody.get("accessToken").asText();
        MockCookie refreshTokenCookie = extractRefreshTokenCookie(loginResult);

        mockMvc.perform(post("/api/accounts/logout")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Authorization", "Bearer " + accessToken)
                        .cookie(refreshTokenCookie)
                        .content("""
                                {
                                  "allDevices": false
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("로그아웃 완료"));

        mockMvc.perform(get("/api/me")
                        .header("Authorization", "Bearer " + accessToken))
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
                        .cookie(extractRefreshTokenCookie(loginResult))
                        .content("""
                                {
                                  "rotate": true
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andReturn();

        MockCookie rotatedRefreshToken = extractRefreshTokenCookie(refreshResult);

        mockMvc.perform(post("/api/accounts/refreshToken")
                        .contentType(MediaType.APPLICATION_JSON)
                        .cookie(extractRefreshTokenCookie(loginResult))
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

        JsonNode loginBody = objectMapper.readTree(loginResult.getResponse().getContentAsString());
        String accessToken = loginBody.get("accessToken").asText();

        MvcResult applyStartResult = mockMvc.perform(post("/api/home/hairapplystart")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "accessToken": "%s",
                                  "hairID": 1
                                }
                                """.formatted(accessToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andReturn();

        JsonNode applyStartBody = objectMapper.readTree(applyStartResult.getResponse().getContentAsString());
        String applySessionId = applyStartBody.get("applySessionId").asText();

        mockMvc.perform(get("/api/home/hairapplystatus/{applySessionId}", applySessionId)
                        .header("Authorization", "Bearer " + accessToken))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.applySessionId").value(applySessionId))
                .andExpect(jsonPath("$.jobType").value("HAIR_APPLY"))
                .andExpect(jsonPath("$.status").value("PENDING"))
                .andExpect(jsonPath("$.hairID").value(1));
    }

    private MockCookie extractRefreshTokenCookie(MvcResult result) {
        String setCookie = result.getResponse().getHeader("Set-Cookie");
        String token = java.util.Arrays.stream(setCookie.split(";"))
                .map(String::trim)
                .filter(part -> part.startsWith("refreshToken="))
                .map(part -> part.substring("refreshToken=".length()))
                .findFirst()
                .orElseThrow();
        return new MockCookie("refreshToken", token);
    }
}
