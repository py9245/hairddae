package com.example.beapp.api.dto.home;

import java.util.List;

import com.example.beapp.api.dto.HairItem;

public record CustomRankResponse(
        int code,
        String message,
        String userID,
        Integer gender,
        Integer age,
        String ageCategory,
        List<HairItem> customRankList
) {
    public static CustomRankResponse ok(String userId, Integer gender, Integer age, String ageCategory, List<HairItem> list) {
        return new CustomRankResponse(200, "조회 정상", userId, gender, age, ageCategory, list);
    }
}
