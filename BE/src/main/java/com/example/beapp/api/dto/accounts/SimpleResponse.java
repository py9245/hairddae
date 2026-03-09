package com.example.beapp.api.dto.accounts;

public record SimpleResponse(
        int code,
        String message
) {
    public static SimpleResponse ok(String message) {
        return new SimpleResponse(200, message);
    }
}
