package com.example.beapp.api.dto.home;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HairClickResponse(
        int code,
        String message,
        boolean success,
        @JsonProperty("hair_id") int hairId
) {
    public static HairClickResponse ok(int hairId) {
        return new HairClickResponse(200, "적용 헤어 기록 완료", true, hairId);
    }
}
