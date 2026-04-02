package com.example.beapp.api.dto.mypage;

import java.util.List;

import com.example.beapp.api.dto.hairs.HairCard;

public record LikeListResponse(
        int code,
        String message,
        String userID,
        List<HairCard> likeList
) {
    public static LikeListResponse ok(String userId, List<HairCard> list) {
        return new LikeListResponse(200, "조회 정상", userId, list);
    }
}
