package com.example.beapp.api.dto.accounts;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record LogoutRequest(
        @NotBlank
        @Size(max = 1024)
        String accessToken,

        @Size(max = 1024)
        String refreshToken,

        Boolean allDevices
) {
}
