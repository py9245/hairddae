package com.example.beapp.api.dto.accounts;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record SignoutRequest(
        @NotBlank
        @Size(max = 1024)
        String accessToken,

        @Size(max = 200)
        String reason,

        @Size(max = 500)
        String feedback
) {
}
