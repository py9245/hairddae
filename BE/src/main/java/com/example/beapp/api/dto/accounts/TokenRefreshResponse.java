package com.example.beapp.api.dto.accounts;

public record TokenRefreshResponse(
        int code,
        String message,
        String accessToken,
        String refreshToken
) {
    public static TokenRefreshResponse ok(String accessToken, String refreshToken) {
        return new TokenRefreshResponse(200, "토큰 재발급 완료", accessToken, refreshToken);
    }
}
