package com.example.beapp.api.dto.home;

import java.util.List;

import com.example.beapp.api.dto.hairs.HairCard;

public record CustomRankResponse(
        int code,
        String message,
        List<HairCard> customList
) {
    public static CustomRankResponse ok(List<HairCard> list) {
        return new CustomRankResponse(200, "조회 정상", list);
    }
}
