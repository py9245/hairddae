package com.example.beapp.api.dto.accounts;

import java.time.LocalDate;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonFormat;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.PastOrPresent;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record SignupRequest(
        @NotBlank @Size(min = 6, max = 20)
        @Pattern(regexp = "^[A-Za-z0-9]+$", message = "영문 및 숫자만 허용")
        String userID,

        @NotBlank
        @Size(min = 8, max = 16)
        @Pattern(
                regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[!@#$%^&*()_+\\-={}\\[\\]:;\"'<>?,./]).{8,16}$",
                message = "영문/숫자/특수문자 각 1개 이상 포함")
        String password,

        @JsonAlias("passwordCheck")
        @NotBlank
        @Size(min = 8, max = 16)
        String passwordConfirm,

        @PastOrPresent
        @JsonFormat(pattern = "yyyy-MM-dd")
        LocalDate birthDate,

        @Pattern(regexp = "^[FM]$", message = "성별은 F 또는 M")
        String gender
) {
}
