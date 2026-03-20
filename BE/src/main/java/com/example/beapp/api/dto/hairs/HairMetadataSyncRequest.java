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

        Boolean active
) {
}
