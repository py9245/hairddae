package com.example.beapp.api.dto.hairs;

import java.time.OffsetDateTime;

public record HairDetailResponse(
        int code,
        String message,
        int hairID,
        String hairName,
        String hairSlug,
        String hairCategory,
        String hairImgpath,
        int hairBookMarkCount,
        int hairDownloadCount,
        OffsetDateTime hairDownloadDate,
        boolean liked,
        String description,
        String datasetCode,
        String datasetRootUrl,
        String assetIndexUrl,
        String representativeAssetId
) {
    public static HairDetailResponse ok(
            int hairID,
            String hairName,
            String hairSlug,
            String hairCategory,
            String hairImgpath,
            int hairBookMarkCount,
            int hairDownloadCount,
            OffsetDateTime hairDownloadDate,
            boolean liked,
            String description,
            String datasetCode,
            String datasetRootUrl,
            String assetIndexUrl,
            String representativeAssetId
    ) {
        return new HairDetailResponse(
                200,
                "조회 정상",
                hairID,
                hairName,
                hairSlug,
                hairCategory,
                hairImgpath,
                hairBookMarkCount,
                hairDownloadCount,
                hairDownloadDate,
                liked,
                description,
                datasetCode,
                datasetRootUrl,
                assetIndexUrl,
                representativeAssetId);
    }
}
