package com.example.beapp.api.dto.home;

import java.util.List;

import com.example.beapp.api.dto.hairs.HairCard;

public record CategoryCardListResponse(
        int code,
        String message,
        String categoryID,
        String categoryName,
        List<HairCard> cardList
) {
    public static CategoryCardListResponse ok(
            String categoryId,
            String categoryName,
            List<HairCard> cardList
    ) {
        return new CategoryCardListResponse(200, "조회 정상", categoryId, categoryName, cardList);
    }
}
