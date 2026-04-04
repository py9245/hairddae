package com.example.beapp.api.dto.camera;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;

public record GetNearbyDesignerRequest(
        @JsonProperty("hair_id")
        @NotNull(message = "hair_id는 필수입니다.")
        Long hairId,

        @NotNull(message = "latitude는 필수입니다.")
        @DecimalMin(value = "-90.0", message = "latitude는 -90 이상이어야 합니다.")
        @DecimalMax(value = "90.0", message = "latitude는 90 이하여야 합니다.")
        Double latitude,

        @NotNull(message = "longitude는 필수입니다.")
        @DecimalMin(value = "-180.0", message = "longitude는 -180 이상이어야 합니다.")
        @DecimalMax(value = "180.0", message = "longitude는 180 이하여야 합니다.")
        Double longitude
) {
}
