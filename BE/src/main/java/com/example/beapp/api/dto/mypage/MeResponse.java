package com.example.beapp.api.dto.mypage;

import java.time.LocalDate;

public record MeResponse(
        int code,
        String message,
        String userID,
        LocalDate birthDate,
        String gender
) {
    public static MeResponse ok(String userId, LocalDate birthDate, String gender) {
        return new MeResponse(200, "조회 정상", userId, birthDate, gender);
    }
}
