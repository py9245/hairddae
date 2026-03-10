package com.example.beapp.api.dto.home;

public record HairApplyResponse(
        int code,
        String message,
        boolean success,
        String applySessionId
) {
    public static HairApplyResponse started(String applySessionId) {
        return new HairApplyResponse(200, "시작 성공", true, applySessionId);
    }
}
