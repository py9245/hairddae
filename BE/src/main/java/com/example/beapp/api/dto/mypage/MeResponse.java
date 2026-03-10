package com.example.beapp.api.dto.mypage;

public record MeResponse(
        int code,
        String message,
        String userID,
        Integer age,
        String gender
) {
    public static MeResponse ok(String userId, Integer age, String gender) {
        return new MeResponse(200, "조회 정상", userId, age, gender);
    }
}
