package com.example.beapp.api.dto.home;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record HairApplyStartV2Request(
        @JsonProperty("hair_id")
        @JsonAlias("hairID")
        @NotNull @Min(1) Integer hairId,
        @JsonProperty("device_id")
        @NotBlank String deviceId,
        @JsonProperty("client_capabilities")
        @Valid ClientCapabilities clientCapabilities
) {
    public record ClientCapabilities(
            @JsonProperty("feature_schema_version")
            Integer featureSchemaVersion,
            @JsonProperty("transform_version")
            String transformVersion
    ) {
    }
}
