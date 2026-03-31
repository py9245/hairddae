package com.example.beapp.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockCookie;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerApplicationRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.GoogleIdTokenVerifier;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;
import com.example.beapp.service.NaverGeocodingClient;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class DesignerApplicationApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserAccountRepository userAccountRepository;

    @Autowired
    private DesignerApplicationRepository designerApplicationRepository;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @MockBean
    private GoogleIdTokenVerifier googleIdTokenVerifier;

    @MockBean
    private NaverGeocodingClient naverGeocodingClient;

    @BeforeEach
    void setUp() {
        designerApplicationRepository.deleteByUserId("TestUser01");
        UserAccount userAccount = userAccountRepository.findByUserId("TestUser01").orElseThrow();
        userAccountRepository.save(new UserAccount(
                userAccount.userID(),
                userAccount.encodedPassword(),
                userAccount.birthDate(),
                userAccount.gender(),
                userAccount.loginType(),
                userAccount.providerSubject(),
                (short) 0));
    }

    @Test
    void designerApplicationRequiresAuthentication() throws Exception {
        mockMvc.perform(post("/api/mypage/designer")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": "CERT-001",
                                  "salonAddress": "서울특별시 강남구",
                                  "acquisitionDate": "2024-01-15"
                                }
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void designerApplicationUpdatesGradeAndStoresRequest() throws Exception {
        MockCookie accessTokenCookie = login();
        given(naverGeocodingClient.geocodeAddress(anyString()))
                .willReturn(new NaverGeocodingClient.GeocodingCoordinates(37.4981, 127.0276));

        mockMvc.perform(post("/api/mypage/designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": "CERT-001",
                                  "salonAddress": "서울특별시 강남구 테헤란로 1",
                                  "acquisitionDate": "2024-01-15"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.message").value("디자이너 신청이 완료되었습니다."));

        mockMvc.perform(get("/api/mypage/user")
                        .cookie(accessTokenCookie))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.grade").value(1));

        var savedApplication = designerApplicationRepository.findByUserId("TestUser01").orElseThrow();
        assertEquals("CERT-001", savedApplication.certificateNumber());
        assertEquals("서울특별시 강남구 테헤란로 1", savedApplication.salonAddress());
        assertEquals(java.time.LocalDate.of(2024, 1, 15), savedApplication.acquisitionDate());
        assertEquals(37.4981, savedApplication.salonLatitude());
        assertEquals(127.0276, savedApplication.salonLongitude());
    }

    @Test
    void designerApplicationNormalizesSalonAddressForGeocodingButStoresOriginalAddress() throws Exception {
        MockCookie accessTokenCookie = login();
        given(naverGeocodingClient.geocodeAddress("서울 노원구 노원로 431 노원역지구대"))
                .willReturn(new NaverGeocodingClient.GeocodingCoordinates(37.654321, 127.061234));

        mockMvc.perform(post("/api/mypage/designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": "CERT-777",
                                  "salonAddress": "(01752) 서울 노원구 노원로 431 노원역지구대",
                                  "acquisitionDate": "2024-01-15"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        then(naverGeocodingClient).should()
                .geocodeAddress("서울 노원구 노원로 431 노원역지구대");

        var savedApplication = designerApplicationRepository.findByUserId("TestUser01").orElseThrow();
        assertEquals("(01752) 서울 노원구 노원로 431 노원역지구대", savedApplication.salonAddress());
        assertEquals(37.654321, savedApplication.salonLatitude());
        assertEquals(127.061234, savedApplication.salonLongitude());
    }

    @Test
    void designerApplicationRejectsDuplicateRequest() throws Exception {
        MockCookie accessTokenCookie = login();
        given(naverGeocodingClient.geocodeAddress(anyString()))
                .willReturn(new NaverGeocodingClient.GeocodingCoordinates(37.4981, 127.0276));

        mockMvc.perform(post("/api/mypage/designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": "CERT-001",
                                  "salonAddress": "서울특별시 강남구 테헤란로 1",
                                  "acquisitionDate": "2024-01-15"
                                }
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/mypage/designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": "CERT-002",
                                  "salonAddress": "서울특별시 송파구 올림픽로 2",
                                  "acquisitionDate": "2023-08-21"
                                }
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value(409));
    }

    @Test
    void designerApplicationRejectsBlankFields() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/mypage/designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "certificateNumber": " ",
                                  "salonAddress": "",
                                  "acquisitionDate": null
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.errors[*].field").isArray());
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
