package com.example.beapp.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerSpecialtyRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.GoogleIdTokenVerifier;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class DesignerSpecialtyApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserAccountRepository userAccountRepository;

    @Autowired
    private DesignerSpecialtyRepository designerSpecialtyRepository;

    @org.springframework.boot.test.mock.mockito.MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @org.springframework.boot.test.mock.mockito.MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @org.springframework.boot.test.mock.mockito.MockBean
    private GoogleIdTokenVerifier googleIdTokenVerifier;

    @BeforeEach
    void setUp() {
        designerSpecialtyRepository.deleteByUserId("TestUser01");
        setUserGrade((short) 2);
    }

    @Test
    void designerSpecialtiesRequireAuthentication() throws Exception {
        mockMvc.perform(post("/api/mypage/designer/specialties")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["가르마"]
                                }
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void approvedDesignerCanSaveAndReadSpecialties() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["가르마", "댄디컷", "가르마"]
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("자신있는 헤어가 저장되었습니다."));

        assertEquals(2, designerSpecialtyRepository.findAllByUserId("TestUser01").size());

        mockMvc.perform(get("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.specialties").isArray())
                .andExpect(jsonPath("$.specialties.length()").value(2))
                .andExpect(jsonPath("$.specialties[0].categoryID").value("가르마"))
                .andExpect(jsonPath("$.specialties[1].categoryID").value("댄디컷"));
    }

    @Test
    void nonDesignerCannotSaveSpecialties() throws Exception {
        setUserGrade((short) 0);
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["가르마"]
                                }
                                """))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value(403));
    }

    @Test
    void specialtiesRejectUnknownCategory() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["없는카테고리"]
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void savingSpecialtiesReplacesPreviousSelections() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["가르마"]
                                }
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(put("/api/mypage/designer/specialties")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "categoryIds": ["댄디컷"]
                                }
                                """))
                .andExpect(status().isOk());

        List<com.example.beapp.model.DesignerSpecialty> saved = designerSpecialtyRepository.findAllByUserId("TestUser01");
        assertEquals(1, saved.size());
        assertEquals("댄디컷", saved.get(0).categoryId());
    }

    private void setUserGrade(short grade) {
        UserAccount userAccount = userAccountRepository.findByUserId("TestUser01").orElseThrow();
        userAccountRepository.save(new UserAccount(
                userAccount.userID(),
                userAccount.encodedPassword(),
                userAccount.birthDate(),
                userAccount.gender(),
                userAccount.loginType(),
                userAccount.providerSubject(),
                grade));
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
