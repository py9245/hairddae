package com.example.beapp.service;

import java.time.LocalDate;
import java.time.Period;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyRequest;
import com.example.beapp.api.dto.home.HairApplyResponse;
import com.example.beapp.api.dto.home.HairApplyStatusResponse;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.api.dto.home.RecodeHairRequest;
import com.example.beapp.api.dto.home.RecodeHairResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.HairApplyJobRepository;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class HomeService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final HairApplyJobRepository hairApplyJobRepository;
    private final HairCatalogService hairCatalogService;

    public HomeService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            HairApplyJobRepository hairApplyJobRepository,
            ObjectProvider<HairCatalogService> hairCatalogServiceProvider) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.hairApplyJobRepository = hairApplyJobRepository;
        this.hairCatalogService = hairCatalogServiceProvider.getIfAvailable();
    }

    public CustomRankResponse getCustomRank(String userId, String ageCategory, Integer gender, int size) {
        UserAccount userAccount = userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));

        Integer resolvedGender = gender != null ? gender : toGenderCode(userAccount.gender());
        Integer resolvedAge = resolveAge(userAccount.birthDate());
        String resolvedAgeCategory = StringUtils.hasText(ageCategory) ? ageCategory : resolveAgeCategory(resolvedAge);

        return CustomRankResponse.ok(
                userId,
                resolvedGender,
                userAccount.birthDate(),
                resolvedAgeCategory,
                hairCatalogService != null
                        ? hairCatalogService.getCustomRankItems(userId, size)
                        : sampleHairRepository.findCustomRankItems());
    }

    public NormalRankResponse getNormalRank(String category, String sort, int size) {
        return NormalRankResponse.ok(
                4000,
                hairCatalogService != null
                        ? hairCatalogService.getNormalRankItems(category, sort, size)
                        : sampleHairRepository.findNormalRankItems());
    }

    public HairApplyResponse startHairApply(HairApplyRequest request, String userId) {
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

    public RecodeHairResponse recordHair(RecodeHairRequest request, String userId) {
        if (hairCatalogService == null) {
            return RecodeHairResponse.ok();
        }
        hairCatalogService.recordHistory(userId, request.hairID(), request.viewSec());
        return RecodeHairResponse.ok();
    }

    private int toGenderCode(String gender) {
        return "M".equalsIgnoreCase(gender) ? 1 : 0;
    }

    private Integer resolveAge(LocalDate birthDate) {
        if (birthDate == null) {
            return 25;
        }
        return Math.max(0, Period.between(birthDate, LocalDate.now()).getYears());
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
