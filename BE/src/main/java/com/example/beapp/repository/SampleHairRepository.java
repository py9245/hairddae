package com.example.beapp.repository;

import java.time.OffsetDateTime;
import java.util.List;

import org.springframework.stereotype.Repository;

import com.example.beapp.api.dto.HairItem;

@Repository
public class SampleHairRepository {

    public List<HairItem> findCustomRankItems() {
        return List.of(sampleHair(301, 2), sampleHair(302, 3));
    }

    public List<HairItem> findNormalRankItems() {
        return List.of(sampleHair(401, 4), sampleHair(402, 5), sampleHair(403, 6));
    }

    public List<HairItem> findRecentItems() {
        return List.of(sampleHair(101, 1), sampleHair(102, 2));
    }

    public List<HairItem> findBookmarkItems() {
        return List.of(sampleHair(201, 1), sampleHair(202, 2));
    }

    private HairItem sampleHair(int id, int daysAgo) {
        return new HairItem(
                id,
                "short",
                "/static/hairs/%d/preview.png".formatted(id),
                12,
                3,
                OffsetDateTime.now().minusDays(daysAgo));
    }
}
