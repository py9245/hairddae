package com.example.beapp.api.dto.camera;

import com.fasterxml.jackson.annotation.JsonProperty;

public record CameraAiUpgradeResponse(
        int code,
        String message,
        boolean success,
        @JsonProperty("request_id") String requestId,
        @JsonProperty("result_image_url") String resultImageUrl
) {
    public static CameraAiUpgradeResponse ok(String requestId, String resultImageUrl) {
        return new CameraAiUpgradeResponse(200, "AI 보정 완료", true, requestId, resultImageUrl);
    }
}
