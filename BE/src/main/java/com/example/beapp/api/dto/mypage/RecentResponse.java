package com.example.beapp.api.dto.mypage;

import java.util.List;

import com.example.beapp.api.dto.hairs.HairCard;

public record RecentResponse(
        int code,
        String message,
        String userID,
        List<HairCard> appliedList
) {
    public static RecentResponse ok(String userId, List<HairCard> list) {
        return new RecentResponse(200, "조회 정상", userId, list);
    }
}
