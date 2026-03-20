package com.example.beapp.api.dto.home;

import java.util.List;

import com.example.beapp.api.dto.hairs.HairCard;

public record NormalRankResponse(
        int code,
        String message,
        List<HairCard> best,
        List<HairCard> latest
) {
    public static NormalRankResponse ok(List<HairCard> best, List<HairCard> latest) {
        return new NormalRankResponse(200, "조회 정상", best, latest);
    }
}
