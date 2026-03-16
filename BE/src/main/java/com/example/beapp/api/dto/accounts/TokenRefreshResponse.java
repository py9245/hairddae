package com.example.beapp.api.dto.accounts;

public record TokenRefreshResponse(
        int code,
        String message
) {
    public static TokenRefreshResponse ok() {
        return new TokenRefreshResponse(200, "재발급 성공");
    }
}
