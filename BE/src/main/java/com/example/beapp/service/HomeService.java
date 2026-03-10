package com.example.beapp.service;

import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyRequest;
import com.example.beapp.api.dto.home.HairApplyResponse;
import com.example.beapp.api.dto.home.HairApplyStatusResponse;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.HairApplyJobRepository;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.JwtTokenService;

@Service
public class HomeService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final HairApplyJobRepository hairApplyJobRepository;
    private final JwtTokenService jwtTokenService;

    public HomeService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            HairApplyJobRepository hairApplyJobRepository,
            JwtTokenService jwtTokenService) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.hairApplyJobRepository = hairApplyJobRepository;
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
        String userId = jwtTokenService.validateAccessToken(accessToken).userId();
        HairApplyJobRepository.HairApplyJobSnapshot jobSnapshot = hairApplyJobRepository.createPending(userId, request.hairID());
        return HairApplyResponse.started(jobSnapshot.id().toString());
    }

    public HairApplyStatusResponse getHairApplyStatus(String userId, String applySessionId) {
        java.util.UUID jobId = parseJobId(applySessionId);
        HairApplyJobRepository.HairApplyJobSnapshot jobSnapshot = hairApplyJobRepository.findById(jobId)
                .orElseThrow(() -> new ApiException(ErrorCode.JOB_NOT_FOUND));

        if (!userId.equals(jobSnapshot.userId())) {
            throw new ApiException(ErrorCode.UNAUTHORIZED, "다른 사용자의 작업에는 접근할 수 없습니다.");
        }

        return HairApplyStatusResponse.ok(
                jobSnapshot.id().toString(),
                jobSnapshot.jobType(),
                jobSnapshot.status(),
                jobSnapshot.hairId(),
                jobSnapshot.completedAt());
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

    private java.util.UUID parseJobId(String applySessionId) {
        try {
            return java.util.UUID.fromString(applySessionId);
        } catch (IllegalArgumentException exception) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "작업 ID 형식이 올바르지 않습니다.");
        }
    }
}
