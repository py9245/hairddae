package com.example.beapp.api;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.example.beapp.model.DesignerApplication;
import com.example.beapp.model.DesignerSpecialty;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerApplicationRepository;
import com.example.beapp.repository.DesignerSpecialtyRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.GoogleIdTokenVerifier;
import com.example.beapp.service.CategoryMetadataSyncService;
import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class NearbyDesignerApiIntegrationTest {

    private static final String DESIGNER_NEAR = "DesignerNear";
    private static final String DESIGNER_FAR = "DesignerFar";
    private static final String DESIGNER_OTHER = "DesignerOther";
    private static final String DESIGNER_NO_COORDS = "DesignerNoCoords";
    private static final String DESIGNER_GRADE_ONE = "DesignerGradeOne";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private UserAccountRepository userAccountRepository;

    @Autowired
    private DesignerSpecialtyRepository designerSpecialtyRepository;

    @Autowired
    private DesignerApplicationRepository designerApplicationRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @MockBean
    private HairMetadataSyncService hairMetadataSyncService;

    @MockBean
    private CategoryMetadataSyncService categoryMetadataSyncService;

    @MockBean
    private GoogleIdTokenVerifier googleIdTokenVerifier;

    @BeforeEach
    void setUp() {
        clearUser(DESIGNER_NEAR);
        clearUser(DESIGNER_FAR);
        clearUser(DESIGNER_OTHER);
        clearUser(DESIGNER_NO_COORDS);
        clearUser(DESIGNER_GRADE_ONE);

        saveUser(DESIGNER_NEAR, (short) 2);
        saveUser(DESIGNER_FAR, (short) 2);
        saveUser(DESIGNER_OTHER, (short) 2);
        saveUser(DESIGNER_NO_COORDS, (short) 2);
        saveUser(DESIGNER_GRADE_ONE, (short) 1);

        designerSpecialtyRepository.saveAll(List.of(
                new DesignerSpecialty(DESIGNER_NEAR, "가르마"),
                new DesignerSpecialty(DESIGNER_FAR, "가르마"),
                new DesignerSpecialty(DESIGNER_OTHER, "댄디컷"),
                new DesignerSpecialty(DESIGNER_NO_COORDS, "가르마"),
                new DesignerSpecialty(DESIGNER_GRADE_ONE, "가르마")
        ));

        designerApplicationRepository.save(new DesignerApplication(
                DESIGNER_NEAR,
                "CERT-NEAR",
                "서울특별시 강남구 테헤란로 212",
                LocalDate.of(2024, 1, 1),
                37.5012748,
                127.0396250));
        designerApplicationRepository.save(new DesignerApplication(
                DESIGNER_FAR,
                "CERT-FAR",
                "서울특별시 서초구 서초대로 77",
                LocalDate.of(2024, 1, 1),
                37.4930000,
                127.0170000));
        designerApplicationRepository.save(new DesignerApplication(
                DESIGNER_OTHER,
                "CERT-OTHER",
                "서울특별시 강남구 봉은사로 1",
                LocalDate.of(2024, 1, 1),
                37.5050000,
                127.0300000));
        designerApplicationRepository.save(new DesignerApplication(
                DESIGNER_NO_COORDS,
                "CERT-NO-COORDS",
                "서울특별시 송파구 올림픽로 300",
                LocalDate.of(2024, 1, 1),
                null,
                null));
        designerApplicationRepository.save(new DesignerApplication(
                DESIGNER_GRADE_ONE,
                "CERT-GRADE-ONE",
                "서울특별시 강남구 역삼로 1",
                LocalDate.of(2024, 1, 1),
                37.5000000,
                127.0300000));
    }

    @Test
    void getNearbyDesignersRequiresAuthentication() throws Exception {
        mockMvc.perform(post("/api/camera/get-designer")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": 5,
                                  "latitude": 37.503222148427824,
                                  "longitude": 127.02794220562396
                                }
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void getNearbyDesignersReturnsOnlyMatchingApprovedDesignersSortedByDistance() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/camera/get-designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": 5,
                                  "latitude": 37.503222148427824,
                                  "longitude": 127.02794220562396
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.designers").isArray())
                .andExpect(jsonPath("$.designers.length()").value(2))
                .andExpect(jsonPath("$.designers[0].userId").value(DESIGNER_NEAR))
                .andExpect(jsonPath("$.designers[1].userId").value(DESIGNER_FAR))
                .andExpect(jsonPath("$.designers[0].salonAddress").value("서울특별시 강남구 테헤란로 212"))
                .andExpect(jsonPath("$.designers[0].distanceKm").isNumber());
    }

    @Test
    void getNearbyDesignersReturnsNotFoundWhenHairDoesNotExist() throws Exception {
        MockCookie accessTokenCookie = login();

        mockMvc.perform(post("/api/camera/get-designer")
                        .cookie(accessTokenCookie)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "hair_id": 999,
                                  "latitude": 37.503222148427824,
                                  "longitude": 127.02794220562396
                                }
                                """))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value(404));
    }

    private void clearUser(String userId) {
        designerSpecialtyRepository.deleteByUserId(userId);
        designerApplicationRepository.deleteByUserId(userId);
        userAccountRepository.deleteByUserId(userId);
    }

    private void saveUser(String userId, short grade) {
        userAccountRepository.save(new UserAccount(
                userId,
                passwordEncoder.encode("P@ssw0rd1"),
                LocalDate.of(1995, 1, 1),
                "M",
                com.example.beapp.model.LoginType.LOCAL,
                null,
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
