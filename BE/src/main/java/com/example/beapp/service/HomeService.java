package com.example.beapp.service;

import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.CategoryCardListResponse;
import com.example.beapp.api.dto.home.CategoryListResponse;
import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairClickRequest;
import com.example.beapp.api.dto.home.HairClickResponse;
import com.example.beapp.api.dto.home.HairApplyResumeV2Request;
import com.example.beapp.api.dto.home.HairApplyStartV2Request;
import com.example.beapp.api.dto.home.HairApplyV2Response;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.api.dto.home.RecodeHairRequest;
import com.example.beapp.api.dto.home.RecodeHairResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.example.beapp.repository.HairApplyJobRepository;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class HomeService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final HairApplyJobRepository hairApplyJobRepository;
    private final HairCatalogService hairCatalogService;
    private final HairJpaRepository hairJpaRepository;
    private final InferenceSessionBootstrapFactory inferenceSessionBootstrapFactory;

    public HomeService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            HairApplyJobRepository hairApplyJobRepository,
            ObjectProvider<HairCatalogService> hairCatalogServiceProvider,
            ObjectProvider<HairJpaRepository> hairJpaRepositoryProvider,
            InferenceSessionBootstrapFactory inferenceSessionBootstrapFactory) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.hairApplyJobRepository = hairApplyJobRepository;
        this.hairCatalogService = hairCatalogServiceProvider.getIfAvailable();
        this.hairJpaRepository = hairJpaRepositoryProvider.getIfAvailable();
        this.inferenceSessionBootstrapFactory = inferenceSessionBootstrapFactory;
    }

    public CustomRankResponse getCustomRank(String userId) {
        verifyUserExists(userId);
        return CustomRankResponse.ok(
                hairCatalogService != null
                        ? hairCatalogService.getCustomRankCards(userId)
                        : sampleHairRepository.findCustomRankCards());
    }

    public NormalRankResponse getNormalRank(String userId) {
        return NormalRankResponse.ok(
                hairCatalogService != null
                        ? hairCatalogService.getBestRankCards(userId)
                        : sampleHairRepository.findBestRankCards(),
                hairCatalogService != null
                        ? hairCatalogService.getLatestRankCards(userId)
                        : sampleHairRepository.findLatestRankCards());
    }

    public CategoryListResponse getCategoryList() {
        return CategoryListResponse.ok(
                hairCatalogService != null
                        ? hairCatalogService.getCategoryItems()
                        : sampleHairRepository.findCategoryItems());
    }

    public CategoryCardListResponse getCategoryCardList(String userId, String categoryId) {
        String resolvedCategoryId = StringUtils.hasText(categoryId) ? categoryId : "all";
        String resolvedCategoryName = "all".equalsIgnoreCase(resolvedCategoryId) ? "전체" : resolvedCategoryId;
        return CategoryCardListResponse.ok(
                resolvedCategoryId,
                resolvedCategoryName,
                hairCatalogService != null
                        ? hairCatalogService.getCategoryCards(userId, resolvedCategoryId)
                        : sampleHairRepository.findCategoryCards(resolvedCategoryId));
    }

    public HairApplyV2Response startHairApplyV2(HairApplyStartV2Request request, String userId) {
        HairApplyJobRepository.HairApplyJobSnapshot jobSnapshot = hairApplyJobRepository.createPending(userId, request.hairId());
        return toHairApplyV2Response(
                jobSnapshot.id(),
                userId,
                request.deviceId(),
                request.hairId());
    }

    public HairApplyV2Response resumeHairApplyV2(HairApplyResumeV2Request request, String userId) {
        UUID jobId = parseJobId(request.applySessionId());
        HairApplyJobRepository.HairApplyJobSnapshot jobSnapshot = hairApplyJobRepository.findById(jobId)
                .orElseThrow(() -> new ApiException(ErrorCode.JOB_NOT_FOUND));

        if (!userId.equals(jobSnapshot.userId())) {
            throw new ApiException(ErrorCode.UNAUTHORIZED, "다른 사용자의 작업에는 접근할 수 없습니다.");
        }
        if (jobSnapshot.hairId() == null) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "헤어 적용 세션에 hairId가 없습니다.");
        }

        return toHairApplyV2Response(
                jobSnapshot.id(),
                userId,
                request.deviceId(),
                jobSnapshot.hairId());
    }

    public RecodeHairResponse recordHair(RecodeHairRequest request, String userId) {
        if (hairCatalogService == null) {
            return RecodeHairResponse.ok();
        }
        hairCatalogService.recordHistory(userId, request.hairID(), request.viewSec());
        return RecodeHairResponse.ok();
    }

    public HairClickResponse recordAppliedHair(HairClickRequest request, String userId) {
        verifyUserExists(userId);
        if (hairCatalogService == null) {
            return HairClickResponse.ok(request.hairId());
        }
        hairCatalogService.recordHistory(userId, request.hairId(), request.viewSec());
        return HairClickResponse.ok(request.hairId());
    }

    private UUID parseJobId(String applySessionId) {
        try {
            return UUID.fromString(applySessionId);
        } catch (IllegalArgumentException exception) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "작업 ID 형식이 올바르지 않습니다.");
        }
    }

    private HairApplyV2Response toHairApplyV2Response(
            UUID jobId,
            String userId,
            String deviceId,
            Integer hairId) {
        ResolvedHairBootstrap bootstrap = resolveHairBootstrap(hairId);
        var ticket = inferenceSessionBootstrapFactory.issueConnectTicket(
                userId,
                jobId.toString(),
                deviceId,
                hairId,
                bootstrap.datasetCode(),
                bootstrap.representativeAssetId());

        return HairApplyV2Response.ok(
                jobId.toString(),
                inferenceSessionBootstrapFactory.featureSchemaVersion(),
                inferenceSessionBootstrapFactory.transformVersion(),
                inferenceSessionBootstrapFactory.buildInferenceConnection(ticket),
                inferenceSessionBootstrapFactory.buildRtcConnection(ticket));
    }

    private ResolvedHairBootstrap resolveHairBootstrap(Integer hairId) {
        if (hairJpaRepository == null) {
            return fallbackBootstrap(hairId);
        }

        return hairJpaRepository.findByIdAndActiveTrue(hairId.longValue())
                .map(this::toResolvedHairBootstrap)
                .orElseGet(() -> fallbackBootstrap(hairId));
    }

    private ResolvedHairBootstrap toResolvedHairBootstrap(HairEntity hair) {
        String datasetCode = StringUtils.hasText(hair.getDatasetCode()) ? hair.getDatasetCode() : "0001";
        return new ResolvedHairBootstrap(
                datasetCode,
                hair.getRepresentativeAssetId());
    }

    private ResolvedHairBootstrap fallbackBootstrap(Integer hairId) {
        return new ResolvedHairBootstrap("0001", null);
    }

    private void verifyUserExists(String userId) {
        getRequiredUser(userId);
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private record ResolvedHairBootstrap(
            String datasetCode,
            String representativeAssetId
    ) {
    }
}
