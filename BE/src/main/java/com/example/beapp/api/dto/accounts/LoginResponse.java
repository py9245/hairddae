package com.example.beapp.api.dto.accounts;

public record LoginResponse(
        int code,
        String message,
        String userID,
        String accessToken,
        String refreshToken
) {
    public static LoginResponse ok(String userId, String accessToken, String refreshToken) {
        return new LoginResponse(200, "로그인 성공", userId, accessToken, refreshToken);
    }
}
