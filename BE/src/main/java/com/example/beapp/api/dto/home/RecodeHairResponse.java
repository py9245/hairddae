package com.example.beapp.api.dto.home;

public record RecodeHairResponse(
        int code,
        String message,
        boolean success
) {
    public static RecodeHairResponse ok() {
        return new RecodeHairResponse(200, "기록 완료", true);
    }
}
