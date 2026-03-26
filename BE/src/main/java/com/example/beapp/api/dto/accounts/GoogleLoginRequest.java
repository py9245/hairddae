package com.example.beapp.api.dto.accounts;

import java.util.Locale;

import com.fasterxml.jackson.annotation.JsonAlias;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record GoogleLoginRequest(
        @JsonAlias({"userID", "googleEmail"})
        @NotBlank
        @Email
        @Size(max = 50)
        String email
) {
    public String normalizedEmail() {
        return email.trim().toLowerCase(Locale.ROOT);
    }
}
