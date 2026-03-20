package com.example.beapp.api.dto.accounts;

import jakarta.validation.constraints.Size;

public record SignoutRequest(
        @Size(max = 200)
        String reason,

        @Size(max = 500)
        String feedback
) {
}
