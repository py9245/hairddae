package com.example.beapp.api.dto.mypage;

public record UserIdResponse(
        int code,
        String message,
        String userID
) {
    public static UserIdResponse ok(String userId) {
        return new UserIdResponse(200, "조회 정상", userId);
    }
}
