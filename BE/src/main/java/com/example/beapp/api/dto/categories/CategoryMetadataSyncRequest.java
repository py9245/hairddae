package com.example.beapp.api.dto.categories;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CategoryMetadataSyncRequest(
        @JsonProperty("category_id")
        @NotBlank(message = "category_id는 필수입니다.")
        @Pattern(regexp = "^[A-Za-z0-9_-]+$", message = "category_id 형식이 올바르지 않습니다.")
        @Size(max = 50, message = "category_id는 50자 이하여야 합니다.")
        String categoryId,

        @JsonProperty("category_name")
        @NotBlank(message = "category_name은 필수입니다.")
        @Size(max = 120, message = "category_name은 120자 이하여야 합니다.")
        String categoryName,

        @Size(max = 5000, message = "description은 5000자 이하여야 합니다.")
        String description,

        @JsonProperty("preview_image_url")
        @Size(max = 500, message = "preview_image_url은 500자 이하여야 합니다.")
        String previewImageUrl,

        @JsonProperty("display_order")
        @Min(value = 0, message = "display_order는 0 이상이어야 합니다.")
        Integer displayOrder,

        Boolean active
) {
}
