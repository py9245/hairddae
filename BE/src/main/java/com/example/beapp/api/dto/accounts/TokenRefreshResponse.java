package com.example.beapp.api.dto.accounts;

public record TokenRefreshResponse(
        int code,
        String message,
        String accessToken,
        String refreshToken
) {
    public static TokenRefreshResponse ok(String accessToken, String refreshToken) {
        return new TokenRefreshResponse(200, "재발급 성공", accessToken, refreshToken);
    }
}
