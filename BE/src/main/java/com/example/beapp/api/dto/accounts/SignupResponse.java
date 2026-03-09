package com.example.beapp.api.dto.accounts;

public record SignupResponse(
        int code,
        String message,
        String userID
) {
    public static SignupResponse created(String userId) {
        return new SignupResponse(201, "회원가입 성공", userId);
    }
}
