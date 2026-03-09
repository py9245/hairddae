package com.example.beapp.api.dto.mypage;

import java.util.List;

import com.example.beapp.api.dto.HairItem;

public record RecentResponse(
        int code,
        String message,
        String userID,
        List<HairItem> recentList
) {
    public static RecentResponse ok(String userId, List<HairItem> list) {
        return new RecentResponse(200, "조회 정상", userId, list);
    }
}
