package com.example.beapp.api.dto.home;

import java.util.List;

import com.example.beapp.api.dto.HairItem;

public record NormalRankResponse(
        int code,
        String message,
        long totalCount,
        List<HairItem> nomalRankList
) {
    public static NormalRankResponse ok(long totalCount, List<HairItem> list) {
        return new NormalRankResponse(200, "조회 정상", totalCount, list);
    }
}
