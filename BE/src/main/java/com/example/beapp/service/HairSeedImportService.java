package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
@Profile("!test")
public class HairSeedImportService {

    private static final Logger log = LoggerFactory.getLogger(HairSeedImportService.class);
    private static final List<DatasetSeedDefinition> DATASET_DEFINITIONS = List.of(
            new DatasetSeedDefinition("0001", "leaf cut", "leaf-cut", "short"),
            new DatasetSeedDefinition("0002", "Hair 2", "hair-2", "short"));

    private final ObjectMapper objectMapper;
    private final HairJpaRepository hairJpaRepository;
    private final AppHairProperties appHairProperties;

    public HairSeedImportService(
            ObjectMapper objectMapper,
            HairJpaRepository hairJpaRepository,
            AppHairProperties appHairProperties) {
        this.objectMapper = objectMapper;
        this.hairJpaRepository = hairJpaRepository;
        this.appHairProperties = appHairProperties;
    }

    @Transactional
    public void importDefaultDatasetIfPresent() {
        for (DatasetSeedDefinition definition : DATASET_DEFINITIONS) {
            importDatasetIfPresent(definition);
        }
    }

    private void importDatasetIfPresent(DatasetSeedDefinition definition) {
        Path datasetRoot = appHairProperties.staticRootPath().resolve(definition.datasetCode());
        Path assetIndexPath = datasetRoot.resolve("manifests").resolve("asset_index_v0.json");
        if (!Files.isRegularFile(assetIndexPath)) {
            log.info("Hair seed import skipped. Missing asset index: {}", assetIndexPath);
            return;
        }

        try {
            AssetIndexPayload payload = objectMapper.readValue(assetIndexPath.toFile(), AssetIndexPayload.class);
            AssetIndexItem representative = selectRepresentativeItem(definition.datasetCode(), payload.items());
            Path representativeMetadataPath = datasetRoot.resolve(representative.metadataPath());
            Map<String, Object> metadata = objectMapper.readValue(
                    representativeMetadataPath.toFile(),
                    new TypeReference<Map<String, Object>>() {
                    });

            String datasetRootUrl = buildUrl(definition.datasetCode());
            String previewImageUrl = buildRepresentativePreviewUrl(datasetRoot, datasetRootUrl, metadata, representative);
            String assetIndexUrl = buildUrl(definition.datasetCode() + "/manifests/asset_index_v0.json");

            HairEntity hair = hairJpaRepository.findByDatasetCode(definition.datasetCode())
                    .or(() -> hairJpaRepository.findBySlug(definition.slug()))
                    .orElseGet(() -> new HairEntity(
                            definition.name(),
                            definition.category(),
                            previewImageUrl,
                            defaultDescription(definition.datasetCode())));

            hair.applySeed(
                    definition.name(),
                    definition.slug(),
                    definition.category(),
                    definition.datasetCode(),
                    datasetRootUrl,
                    assetIndexUrl,
                    representative.assetId(),
                    previewImageUrl,
                    defaultDescription(definition.datasetCode()));
            hairJpaRepository.save(hair);
            log.info(
                    "Hair seed import completed. datasetCode={}, representativeAssetId={}",
                    definition.datasetCode(),
                    representative.assetId());
        } catch (IOException exception) {
            throw new IllegalStateException(
                    "Failed to import hair dataset seed from " + assetIndexPath,
                    exception);
        }
    }

    private AssetIndexItem selectRepresentativeItem(String datasetCode, List<AssetIndexItem> items) {
        List<AssetIndexItem> approvedItems = items.stream()
                .filter(item -> Boolean.TRUE.equals(item.approved()))
                .toList();
        List<AssetIndexItem> selectableItems = approvedItems.isEmpty() ? items : approvedItems;

        return selectableItems.stream()
                .min(
                        Comparator.comparingInt(this::posePenalty)
                                .thenComparing(
                                        item -> Optional.ofNullable(item.qualityScore()).orElse(0.0),
                                        Comparator.reverseOrder()))
                .orElseThrow(() -> new IllegalStateException("No selectable assets found in dataset " + datasetCode));
    }

    private int posePenalty(AssetIndexItem item) {
        return Math.abs(Optional.ofNullable(item.yaw1deg()).orElse(0)) * 2
                + Math.abs(Optional.ofNullable(item.pitch1deg()).orElse(0))
                + Math.abs(Optional.ofNullable(item.roll1deg()).orElse(0));
    }

    private String buildRepresentativePreviewUrl(
            Path datasetRoot,
            String datasetRootUrl,
            Map<String, Object> metadata,
            AssetIndexItem representative
    ) {
        String hairRgbaPath = stringValue(metadata.get("hair_rgba_path"));
        if (StringUtils.hasText(hairRgbaPath) && Files.isRegularFile(datasetRoot.resolve(hairRgbaPath))) {
            return datasetRootUrl + "/" + normalizeRelativePath(hairRgbaPath);
        }

        String imagePath = stringValue(metadata.get("image_path"));
        if (StringUtils.hasText(imagePath) && Files.isRegularFile(datasetRoot.resolve(imagePath))) {
            return datasetRootUrl + "/" + normalizeRelativePath(imagePath);
        }

        return datasetRootUrl + "/hair_rgba/" + representative.assetId() + ".png";
    }

    private String buildUrl(String relativePath) {
        String baseUrl = trimTrailingSlash(appHairProperties.staticBaseUrl());
        return baseUrl + "/" + normalizeRelativePath(relativePath);
    }

    private String trimTrailingSlash(String value) {
        return value != null && value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private String normalizeRelativePath(String value) {
        return value.startsWith("/") ? value.substring(1) : value;
    }

    private String stringValue(Object value) {
        return value instanceof String string ? string : null;
    }

    private String defaultDescription(String datasetCode) {
        return "Hair dataset imported from static asset pack " + datasetCode + ".";
    }

    private record DatasetSeedDefinition(
            String datasetCode,
            String name,
            String slug,
            String category
    ) {
    }

    private record AssetIndexPayload(
            Map<String, Object> summary,
            List<AssetIndexItem> items
    ) {
    }

    private record AssetIndexItem(
            @JsonProperty("asset_id") String assetId,
            @JsonProperty("metadata_path") String metadataPath,
            @JsonProperty("yaw_1deg") Integer yaw1deg,
            @JsonProperty("pitch_1deg") Integer pitch1deg,
            @JsonProperty("roll_1deg") Integer roll1deg,
            @JsonProperty("quality_score") Double qualityScore,
            Boolean approved
    ) {
    }
}
