package com.example.beapp.api.dto.home;

import java.util.List;

public record CategoryListResponse(
        int code,
        String message,
        List<CategoryItem> categoryList
) {
    public static CategoryListResponse ok(List<CategoryItem> categoryList) {
        return new CategoryListResponse(200, "조회 정상", categoryList);
    }

    public record CategoryItem(
            String categoryID,
            String categoryName,
            String image
    ) {
    }
}
