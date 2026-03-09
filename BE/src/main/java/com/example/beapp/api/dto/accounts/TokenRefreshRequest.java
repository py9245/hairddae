package com.example.beapp.api.dto.accounts;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record TokenRefreshRequest(
        @NotBlank
        @Size(max = 1024)
        String refreshToken,

        @Size(max = 1024)
        String accessToken,

        Boolean rotate
) {
}
