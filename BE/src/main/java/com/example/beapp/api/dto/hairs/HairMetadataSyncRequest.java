package com.example.beapp.api.dto.hairs;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record HairMetadataSyncRequest(
        @JsonProperty("dataset_code")
        @NotBlank(message = "dataset_code는 필수입니다.")
        @Pattern(regexp = "^[A-Za-z0-9_-]+$", message = "dataset_code 형식이 올바르지 않습니다.")
        @Size(max = 50, message = "dataset_code는 50자 이하여야 합니다.")
        String datasetCode,

        @NotBlank(message = "name은 필수입니다.")
        @Size(max = 120, message = "name은 120자 이하여야 합니다.")
        String name,

        @NotBlank(message = "slug는 필수입니다.")
        @Pattern(regexp = "^[a-z0-9-]+$", message = "slug 형식이 올바르지 않습니다.")
        @Size(max = 120, message = "slug는 120자 이하여야 합니다.")
        String slug,

        @NotBlank(message = "category는 필수입니다.")
        @Size(max = 50, message = "category는 50자 이하여야 합니다.")
        String category,

        @Size(max = 5000, message = "description은 5000자 이하여야 합니다.")
        String description,

        @JsonProperty("dataset_root_url")
        @Size(max = 500, message = "dataset_root_url은 500자 이하여야 합니다.")
        String datasetRootUrl,

        @JsonProperty("asset_index_url")
        @Size(max = 500, message = "asset_index_url은 500자 이하여야 합니다.")
        String assetIndexUrl,

        @JsonProperty("representative_asset_id")
        @Size(max = 255, message = "representative_asset_id는 255자 이하여야 합니다.")
        String representativeAssetId,

        @JsonProperty("preview_image_url")
        @Size(max = 500, message = "preview_image_url은 500자 이하여야 합니다.")
        String previewImageUrl,

        Boolean active
) {
}
