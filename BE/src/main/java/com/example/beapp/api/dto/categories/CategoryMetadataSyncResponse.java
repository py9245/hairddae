package com.example.beapp.api.dto.categories;

import com.fasterxml.jackson.annotation.JsonProperty;

public record CategoryMetadataSyncResponse(
        int code,
        String message,
        @JsonProperty("category_id") String categoryId,
        boolean created
) {
    public static CategoryMetadataSyncResponse ok(String categoryId, boolean created) {
        return new CategoryMetadataSyncResponse(
                200,
                created ? "카테고리 메타데이터 등록 완료" : "카테고리 메타데이터 갱신 완료",
                categoryId,
                created);
    }
}
