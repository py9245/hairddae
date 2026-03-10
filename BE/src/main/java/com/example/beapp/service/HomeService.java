package com.example.beapp.service;

import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyRequest;
import com.example.beapp.api.dto.home.HairApplyResponse;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.JwtTokenService;

@Service
public class HomeService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final JwtTokenService jwtTokenService;

    public HomeService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            JwtTokenService jwtTokenService) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.jwtTokenService = jwtTokenService;
    }

    public CustomRankResponse getCustomRank(String userId, String ageCategory, Integer gender) {
        UserAccount userAccount = userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));

        Integer resolvedGender = gender != null ? gender : toGenderCode(userAccount.gender());
        Integer resolvedAge = userAccount.age() != null ? userAccount.age() : 25;
        String resolvedAgeCategory = StringUtils.hasText(ageCategory) ? ageCategory : resolveAgeCategory(resolvedAge);

        return CustomRankResponse.ok(
                userId,
                resolvedGender,
                resolvedAge,
                resolvedAgeCategory,
                sampleHairRepository.findCustomRankItems());
    }

    public NormalRankResponse getNormalRank() {
        return NormalRankResponse.ok(4000, sampleHairRepository.findNormalRankItems());
    }

    public HairApplyResponse startHairApply(HairApplyRequest request, String authorizationHeader) {
        String bearerToken = jwtTokenService.extractBearerToken(authorizationHeader);
        String accessToken = StringUtils.hasText(bearerToken) ? bearerToken : request.accessToken();
        jwtTokenService.validateAccessToken(accessToken);
        return HairApplyResponse.started(UUID.randomUUID().toString());
    }

    private int toGenderCode(String gender) {
        return "M".equalsIgnoreCase(gender) ? 1 : 0;
    }

    private String resolveAgeCategory(Integer age) {
        int safeAge = age == null ? 25 : age;
        int start = (safeAge / 5) * 5;
        int end = Math.min(start + 4, 119);
        return "%02d_%02d".formatted(start, end);
    }
}
