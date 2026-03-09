package com.example.beapp.api.dto.accounts;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record LoginRequest(
        @NotBlank @Size(min = 6, max = 20)
        @Pattern(regexp = "^[A-Za-z0-9]+$", message = "영문 및 숫자만 허용")
        String userID,

        @NotBlank
        @Size(min = 8, max = 16)
        @Pattern(
                regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[!@#$%^&*()_+\\-={}\\[\\]:;\"'<>?,./]).{8,16}$",
                message = "영문/숫자/특수문자 각 1개 이상 포함")
        String password
) {
}
