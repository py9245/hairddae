package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.Period;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyResumeV2Request;
import com.example.beapp.api.dto.home.HairApplyStartV2Request;
import com.example.beapp.api.dto.home.HairApplyV2Response;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.api.dto.home.RecodeHairRequest;
import com.example.beapp.api.dto.home.RecodeHairResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.model.UserAccount;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.example.beapp.repository.HairApplyJobRepository;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class HomeService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final HairApplyJobRepository hairApplyJobRepository;
    private final HairCatalogService hairCatalogService;
    private final HairJpaRepository hairJpaRepository;
    private final InferenceSessionBootstrapFactory inferenceSessionBootstrapFactory;
    private final AppHairProperties appHairProperties;
    private final ObjectMapper objectMapper;

    public HomeService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            HairApplyJobRepository hairApplyJobRepository,
            ObjectProvider<HairCatalogService> hairCatalogServiceProvider,
            ObjectProvider<HairJpaRepository> hairJpaRepositoryProvider,
            InferenceSessionBootstrapFactory inferenceSessionBootstrapFactory,
            AppHairProperties appHairProperties,
            ObjectMapper objectMapper) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.hairApplyJobRepository = hairApplyJobRepository;
        this.hairCatalogService = hairCatalogServiceProvider.getIfAvailable();
        this.hairJpaRepository = hairJpaRepositoryProvider.getIfAvailable();
        this.inferenceSessionBootstrapFactory = inferenceSessionBootstrapFactory;
        this.appHairProperties = appHairProperties;
        this.objectMapper = objectMapper;
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
                inferenceSessionBootstrapFactory.buildRtcConnection(ticket),
                new HairApplyV2Response.StaticBootstrap(
                        bootstrap.baseUrl(),
                        bootstrap.datasetCode(),
                        inferenceSessionBootstrapFactory.assetBundleSchemaVersion(),
                        bootstrap.assetIndexUrl(),
                        bootstrap.preloadAssetIds()));
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
        String baseUrl = StringUtils.hasText(hair.getDatasetRootUrl())
                ? trimTrailingSlash(hair.getDatasetRootUrl())
                : trimTrailingSlash(appHairProperties.staticBaseUrl()) + "/" + datasetCode;
        String assetIndexUrl = StringUtils.hasText(hair.getAssetIndexUrl())
                ? hair.getAssetIndexUrl()
                : "/api/hairs/%d/asset-index".formatted(hair.getId());
        List<String> preloadAssetIds = loadPreloadAssetIds(datasetCode, hair.getRepresentativeAssetId());

        return new ResolvedHairBootstrap(
                hair.getId().intValue(),
                datasetCode,
                hair.getRepresentativeAssetId(),
                baseUrl,
                assetIndexUrl,
                preloadAssetIds);
    }

    private ResolvedHairBootstrap fallbackBootstrap(Integer hairId) {
        String datasetCode = "0001";
        return new ResolvedHairBootstrap(
                hairId,
                datasetCode,
                null,
                trimTrailingSlash(appHairProperties.staticBaseUrl()) + "/" + datasetCode,
                "/api/hairs/%d/asset-index".formatted(hairId),
                loadPreloadAssetIds(datasetCode, null));
    }

    private List<String> loadPreloadAssetIds(String datasetCode, String representativeAssetId) {
        Path assetIndexPath = appHairProperties.staticRootPath()
                .resolve(datasetCode)
                .resolve("manifests")
                .resolve("asset_index_v0.json");
        if (!Files.isRegularFile(assetIndexPath)) {
            return representativeAssetId == null ? List.of() : List.of(representativeAssetId);
        }

        try {
            JsonNode itemsNode = objectMapper.readTree(assetIndexPath.toFile()).path("items");
            List<PreloadAssetCandidate> candidates = new java.util.ArrayList<>();
            for (JsonNode itemNode : itemsNode) {
                candidates.add(new PreloadAssetCandidate(
                        itemNode.path("asset_id").asText(),
                        itemNode.path("yaw_1deg").asInt(0),
                        itemNode.path("pitch_1deg").asInt(0),
                        itemNode.path("roll_1deg").asInt(0),
                        itemNode.path("quality_score").asDouble(0.0),
                        itemNode.path("approved").asBoolean(false)));
            }

            List<PreloadAssetCandidate> selectable = candidates.stream()
                    .filter(PreloadAssetCandidate::approved)
                    .toList();
            List<PreloadAssetCandidate> source = selectable.isEmpty() ? candidates : selectable;
            if (source.isEmpty()) {
                return List.of();
            }

            PreloadAssetCandidate representative = source.stream()
                    .filter(candidate -> StringUtils.hasText(representativeAssetId) && representativeAssetId.equals(candidate.assetId()))
                    .findFirst()
                    .orElse(source.getFirst());

            return source.stream()
                    .sorted(Comparator
                            .comparingInt((PreloadAssetCandidate candidate) -> preloadPosePenalty(candidate, representative))
                            .thenComparing(PreloadAssetCandidate::qualityScore, Comparator.reverseOrder()))
                    .limit(3)
                    .map(PreloadAssetCandidate::assetId)
                    .toList();
        } catch (IOException exception) {
            return representativeAssetId == null ? List.of() : List.of(representativeAssetId);
        }
    }

    private int preloadPosePenalty(PreloadAssetCandidate candidate, PreloadAssetCandidate representative) {
        return Math.abs(candidate.yaw1deg() - representative.yaw1deg()) * 2
                + Math.abs(candidate.pitch1deg() - representative.pitch1deg())
                + Math.abs(candidate.roll1deg() - representative.roll1deg());
    }

    private String trimTrailingSlash(String value) {
        return value != null && value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private record ResolvedHairBootstrap(
            Integer hairId,
            String datasetCode,
            String representativeAssetId,
            String baseUrl,
            String assetIndexUrl,
            List<String> preloadAssetIds
    ) {
    }

    private record PreloadAssetCandidate(
            String assetId,
            int yaw1deg,
            int pitch1deg,
            int roll1deg,
            double qualityScore,
            boolean approved
    ) {
    }
}
