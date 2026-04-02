package com.example.beapp.api.dto.hairs;

import java.time.OffsetDateTime;

public record HairCard(
        int hairID,
        String image,
        boolean liked,
        String hookText,
        String hairName,
        String datasetCode,
        String category,
        OffsetDateTime createdAt
) {
}
