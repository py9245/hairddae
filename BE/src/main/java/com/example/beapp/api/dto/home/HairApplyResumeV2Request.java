package com.example.beapp.api.dto.home;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.NotBlank;

public record HairApplyResumeV2Request(
        @JsonProperty("apply_session_id")
        @NotBlank String applySessionId,
        @JsonProperty("device_id")
        @NotBlank String deviceId
) {
}
