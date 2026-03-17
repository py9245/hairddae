package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.hairs.HairAssetIndexV2Response;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
@Profile("!test")
public class HairAssetBundleIndexService {

    private final HairJpaRepository hairJpaRepository;
    private final AppHairProperties appHairProperties;
    private final AppInferenceProperties appInferenceProperties;
    private final ObjectMapper objectMapper;
    private final Map<String, DatasetCache> datasetCache = new ConcurrentHashMap<>();

    public HairAssetBundleIndexService(
            HairJpaRepository hairJpaRepository,
            AppHairProperties appHairProperties,
            AppInferenceProperties appInferenceProperties,
            ObjectMapper objectMapper) {
        this.hairJpaRepository = hairJpaRepository;
        this.appHairProperties = appHairProperties;
        this.appInferenceProperties = appInferenceProperties;
        this.objectMapper = objectMapper;
    }

    public HairAssetIndexV2Response getAssetIndex(Long hairId) {
        HairEntity hair = hairJpaRepository.findByIdAndActiveTrue(hairId)
                .orElseThrow(() -> new ApiException(ErrorCode.HAIR_NOT_FOUND));
        if (!StringUtils.hasText(hair.getDatasetCode())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "헤어 데이터셋 코드가 비어 있습니다.");
        }

        DatasetCache cache = datasetCache.computeIfAbsent(hair.getDatasetCode(), this::loadDatasetCache);
        String datasetRootUrl = StringUtils.hasText(hair.getDatasetRootUrl())
                ? trimTrailingSlash(hair.getDatasetRootUrl())
                : trimTrailingSlash(appHairProperties.staticBaseUrl()) + "/" + hair.getDatasetCode();

        List<HairAssetIndexV2Response.AssetBundleItem> items = cache.items().stream()
                .map(item -> {
                    AssetMetadata metadata = cache.loadMetadata(item.assetId());
                    return new HairAssetIndexV2Response.AssetBundleItem(
                            item.assetId(),
                            firstText(metadata.poseKey(), item.poseKey()),
                            buildAssetUrl(datasetRootUrl, metadata.hairRgbaPath()),
                            buildAssetUrl(datasetRootUrl, item.hairMaskPath()),
                            buildAssetUrl(datasetRootUrl, item.anchorsPath()),
                            buildAssetUrl(datasetRootUrl, item.metadataPath()),
                            toBoundingBox(metadata.hairRgbaBBox()),
                            hair.getDatasetCode() + ":" + item.assetId());
                })
                .toList();

        return HairAssetIndexV2Response.ok(
                hair.getId().intValue(),
                hair.getDatasetCode(),
                appInferenceProperties.assetBundleSchemaVersion(),
                items);
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

    private HairAssetIndexV2Response.BoundingBox toBoundingBox(BoundingBoxValue boundingBox) {
        if (boundingBox == null) {
            return null;
        }
        return new HairAssetIndexV2Response.BoundingBox(
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

    private String normalizeRelativePath(String value) {
        return value.startsWith("/") ? value.substring(1) : value;
    }

    private String trimTrailingSlash(String value) {
        return value != null && value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
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
                    .filter(candidate -> candidate.assetId().equals(assetId))
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
            @JsonProperty("anchors_path") String anchorsPath,
            @JsonProperty("hair_mask_path") String hairMaskPath
    ) {
    }

    private record AssetMetadata(
            @JsonProperty("pose_key") String poseKey,
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
