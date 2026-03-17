package com.example.beapp.api.dto.home;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record HairApplyRequest(
        @NotNull @Min(1) Integer hairID
) {
}
