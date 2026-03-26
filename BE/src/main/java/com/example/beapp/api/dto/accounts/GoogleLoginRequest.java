package com.example.beapp.api.dto.accounts;

import com.fasterxml.jackson.annotation.JsonAlias;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record GoogleLoginRequest(
        @JsonAlias({"credential", "id_token"})
        @NotBlank
        @Size(max = 4096)
        String idToken
) {
}
