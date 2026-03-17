package com.example.beapp.api.dto.hairs;

import java.util.List;

public record HairListResponse(
        int code,
        String message,
        long totalCount,
        List<HairCard> hairList
) {
    public static HairListResponse ok(long totalCount, List<HairCard> hairList) {
        return new HairListResponse(200, "조회 정상", totalCount, hairList);
    }
}
