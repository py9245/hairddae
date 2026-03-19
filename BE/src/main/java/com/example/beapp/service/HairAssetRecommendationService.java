package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.hairs.HairRecommendResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairEntity;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
@Profile("!test")
public class HairAssetRecommendationService {

    private final ObjectMapper objectMapper;
    private final AppHairProperties appHairProperties;
    private final Map<String, DatasetCache> datasetCaches = new ConcurrentHashMap<>();

    public HairAssetRecommendationService(
            ObjectMapper objectMapper,
            AppHairProperties appHairProperties
    ) {
        this.objectMapper = objectMapper;
        this.appHairProperties = appHairProperties;
    }

    public HairRecommendResponse.RecommendedAsset recommend(
            HairEntity hair,
            Integer yaw1deg,
            Integer pitch1deg,
            Integer roll1deg
    ) {
        if (!StringUtils.hasText(hair.getDatasetCode())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "헤어 데이터셋 코드가 비어 있습니다.");
        }
        DatasetCache cache = datasetCaches.computeIfAbsent(hair.getDatasetCode(), this::loadDatasetCache);
        AssetIndexItem selected = selectAsset(cache, hair.getRepresentativeAssetId(), yaw1deg, pitch1deg, roll1deg);
        AssetMetadata metadata = cache.loadMetadata(selected.assetId());
        String datasetRootUrl = StringUtils.hasText(hair.getDatasetRootUrl())
                ? trimTrailingSlash(hair.getDatasetRootUrl())
                : trimTrailingSlash(appHairProperties.staticBaseUrl()) + "/" + hair.getDatasetCode();

        return new HairRecommendResponse.RecommendedAsset(
                selected.assetId(),
                firstText(metadata.poseKey(), selected.poseKey()),
                selected.yaw1deg(),
                selected.pitch1deg(),
                selected.roll1deg(),
                buildAssetUrl(datasetRootUrl, firstText(metadata.imagePath(), selected.imagePath())),
                buildAssetUrl(datasetRootUrl, firstText(metadata.alphaPath(), selected.alphaPath())),
                buildAssetUrl(datasetRootUrl, firstText(metadata.anchorsPath(), selected.anchorsPath())),
                buildAssetUrl(datasetRootUrl, selected.metadataPath()),
                buildAssetUrl(datasetRootUrl, metadata.hairRgbaPath()),
                toBoundingBox(metadata.hairRgbaBBox()),
                selected.qualityScore());
    }

    private DatasetCache loadDatasetCache(String datasetCode) {
        Path datasetRoot = appHairProperties.staticRootPath().resolve(datasetCode);
        Path assetIndexPath = datasetRoot.resolve("manifests").resolve("asset_index_v0.json");
        if (!Files.isRegularFile(assetIndexPath)) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "헤어 데이터셋을 찾을 수 없습니다: " + datasetCode);
        }

        try {
            AssetIndexPayload payload = objectMapper.readValue(assetIndexPath.toFile(), AssetIndexPayload.class);
            return new DatasetCache(datasetRoot, payload.items(), new ConcurrentHashMap<>(), objectMapper);
        } catch (IOException exception) {
            throw new IllegalStateException("헤어 데이터셋 인덱스를 읽지 못했습니다: " + assetIndexPath, exception);
        }
    }

    private AssetIndexItem selectAsset(
            DatasetCache cache,
            String representativeAssetId,
            Integer yaw1deg,
            Integer pitch1deg,
            Integer roll1deg
    ) {
        List<AssetIndexItem> approvedItems = cache.items().stream()
                .filter(item -> Boolean.TRUE.equals(item.approved()))
                .toList();
        List<AssetIndexItem> candidates = approvedItems.isEmpty() ? cache.items() : approvedItems;
        if (candidates.isEmpty()) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "선택 가능한 헤어 에셋이 없습니다.");
        }

        if (yaw1deg == null && pitch1deg == null && roll1deg == null && StringUtils.hasText(representativeAssetId)) {
            return candidates.stream()
                    .filter(item -> representativeAssetId.equals(item.assetId()))
                    .findFirst()
                    .orElse(candidates.getFirst());
        }

        int resolvedYaw = yaw1deg == null ? 0 : yaw1deg;
        int resolvedPitch = pitch1deg == null ? 0 : pitch1deg;
        int resolvedRoll = roll1deg == null ? 0 : roll1deg;

        return candidates.stream()
                .min(Comparator.<AssetIndexItem>comparingInt(
                                item -> posePenalty(item, resolvedYaw, resolvedPitch, resolvedRoll))
                        .thenComparing(
                                item -> item.qualityScore() == null ? 0.0 : item.qualityScore(),
                                Comparator.reverseOrder()))
                .orElseThrow(() -> new ApiException(ErrorCode.INVALID_REQUEST, "선택 가능한 헤어 에셋이 없습니다."));
    }

    private int posePenalty(AssetIndexItem item, int yaw1deg, int pitch1deg, int roll1deg) {
        return Math.abs((item.yaw1deg() == null ? 0 : item.yaw1deg()) - yaw1deg) * 2
                + Math.abs((item.pitch1deg() == null ? 0 : item.pitch1deg()) - pitch1deg)
                + Math.abs((item.roll1deg() == null ? 0 : item.roll1deg()) - roll1deg);
    }

    private HairRecommendResponse.BoundingBox toBoundingBox(BoundingBoxValue boundingBox) {
        if (boundingBox == null) {
            return null;
        }
        return new HairRecommendResponse.BoundingBox(
                boundingBox.x(),
                boundingBox.y(),
                boundingBox.w(),
                boundingBox.h());
    }

    private String buildAssetUrl(String datasetRootUrl, String relativePath) {
        if (!StringUtils.hasText(relativePath)) {
            return null;
        }
        return datasetRootUrl + "/" + normalizeRelativePath(relativePath);
    }

    private String trimTrailingSlash(String value) {
        return value != null && value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private String normalizeRelativePath(String value) {
        return value.startsWith("/") ? value.substring(1) : value;
    }

    private String firstText(String primary, String fallback) {
        return StringUtils.hasText(primary) ? primary : fallback;
    }

    private record DatasetCache(
            Path datasetRoot,
            List<AssetIndexItem> items,
            Map<String, AssetMetadata> metadataCache,
            ObjectMapper objectMapper
    ) {
        private AssetMetadata loadMetadata(String assetId) {
            return metadataCache.computeIfAbsent(assetId, this::readMetadata);
        }

        private AssetMetadata readMetadata(String assetId) {
            AssetIndexItem item = items.stream()
                    .filter(candidate -> Objects.equals(candidate.assetId(), assetId))
                    .findFirst()
                    .orElseThrow(() -> new ApiException(ErrorCode.INVALID_REQUEST, "에셋 메타데이터를 찾을 수 없습니다."));
            Path metadataPath = datasetRoot.resolve(item.metadataPath());
            try {
                return objectMapper.readValue(metadataPath.toFile(), AssetMetadata.class);
            } catch (IOException exception) {
                throw new IllegalStateException("헤어 에셋 메타데이터를 읽지 못했습니다: " + metadataPath, exception);
            }
        }
    }

    private record AssetIndexPayload(
            List<AssetIndexItem> items
    ) {
    }

    private record AssetIndexItem(
            @JsonProperty("asset_id") String assetId,
            @JsonProperty("pose_key") String poseKey,
            @JsonProperty("metadata_path") String metadataPath,
            @JsonProperty("image_path") String imagePath,
            @JsonProperty("alpha_path") String alphaPath,
            @JsonProperty("anchors_path") String anchorsPath,
            @JsonProperty("yaw_1deg") Integer yaw1deg,
            @JsonProperty("pitch_1deg") Integer pitch1deg,
            @JsonProperty("roll_1deg") Integer roll1deg,
            @JsonProperty("quality_score") Double qualityScore,
            Boolean approved
    ) {
    }

    private record AssetMetadata(
            @JsonProperty("pose_key") String poseKey,
            @JsonProperty("image_path") String imagePath,
            @JsonProperty("alpha_path") String alphaPath,
            @JsonProperty("anchors_path") String anchorsPath,
            @JsonProperty("hair_rgba_path") String hairRgbaPath,
            @JsonProperty("hair_rgba_bbox") BoundingBoxValue hairRgbaBBox
    ) {
    }

    private record BoundingBoxValue(
            Integer x,
            Integer y,
            Integer w,
            Integer h
    ) {
    }
}
