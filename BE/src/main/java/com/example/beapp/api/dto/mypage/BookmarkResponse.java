package com.example.beapp.api.dto.mypage;

import java.util.List;

import com.example.beapp.api.dto.HairItem;

public record BookmarkResponse(
        int code,
        String message,
        String userID,
        List<HairItem> bookMarkList
) {
    public static BookmarkResponse ok(String userId, List<HairItem> list) {
        return new BookmarkResponse(200, "조회 정상", userId, list);
    }
}
