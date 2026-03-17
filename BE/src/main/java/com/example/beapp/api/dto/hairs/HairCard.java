package com.example.beapp.api.dto.hairs;

import java.time.OffsetDateTime;

public record HairCard(
        int hairID,
        String hairName,
        String hairSlug,
        String hairCategory,
        String hairImgpath,
        int hairBookMarkCount,
        int hairDownloadCount,
        OffsetDateTime hairDownloadDate,
        boolean liked,
        String datasetCode
) {
}
