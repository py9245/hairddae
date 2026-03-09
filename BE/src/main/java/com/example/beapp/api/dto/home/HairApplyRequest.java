package com.example.beapp.api.dto.home;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record HairApplyRequest(
        @NotBlank @Size(max = 1024) String accessToken,
        @NotNull @Min(1) Integer hairID
) {
}
