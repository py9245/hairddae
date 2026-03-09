package com.example.beapp.api.dto;

import java.time.OffsetDateTime;

public record HairItem(
        int hairID,
        String hairCategory,
        String hairImgpath,
        int hairBookMarkCount,
        int hairDownloadCount,
        OffsetDateTime hairDownloadDate
) {
}
