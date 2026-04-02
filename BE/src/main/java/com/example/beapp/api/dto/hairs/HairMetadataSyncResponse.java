package com.example.beapp.api.dto.hairs;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HairMetadataSyncResponse(
        int code,
        String message,
        @JsonProperty("hair_id") int hairId,
        @JsonProperty("dataset_code") String datasetCode,
        boolean created
) {
    public static HairMetadataSyncResponse ok(int hairId, String datasetCode, boolean created) {
        return new HairMetadataSyncResponse(
                200,
                created ? "헤어 메타데이터 등록 완료" : "헤어 메타데이터 갱신 완료",
                hairId,
                datasetCode,
                created);
    }
}
