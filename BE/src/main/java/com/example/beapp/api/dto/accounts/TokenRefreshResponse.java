package com.example.beapp.api.dto.accounts;

public record TokenRefreshResponse(
        int code,
        String message,
        String accessToken
) {
    public static TokenRefreshResponse ok(String accessToken) {
        return new TokenRefreshResponse(200, "재발급 성공", accessToken);
    }
}
