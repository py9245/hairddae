package com.example.beapp.api.dto.home;

import java.time.OffsetDateTime;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record RecodeHairRequest(
        @Size(max = 1024) String accessToken,
        @NotNull @Min(1) Integer hairID,
        @Min(0) Integer viewSec,
        OffsetDateTime clientTimestamp,
        @Size(max = 36) String requestId
) {
}
