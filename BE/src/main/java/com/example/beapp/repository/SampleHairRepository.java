package com.example.beapp.repository;

import java.time.OffsetDateTime;
import java.util.List;

import org.springframework.stereotype.Repository;

import com.example.beapp.api.dto.hairs.HairCard;
import com.example.beapp.api.dto.home.CategoryListResponse;

@Repository
public class SampleHairRepository {

    public List<HairCard> findCustomRankCards() {
        return List.of(sampleHair(301, "short", 2, true), sampleHair(302, "medium", 3, false));
    }

    public List<HairCard> findBestRankCards() {
        return List.of(sampleHair(401, "short", 4, false), sampleHair(402, "medium", 5, false));
    }

    public List<HairCard> findLatestRankCards() {
        return List.of(sampleHair(403, "short", 1, false), sampleHair(404, "leaf", 2, true));
    }

    public List<CategoryListResponse.CategoryItem> findCategoryItems() {
        return List.of(
                new CategoryListResponse.CategoryItem("all", "전체", "/static/hair-preview/0001/main.png"),
                new CategoryListResponse.CategoryItem("short", "short", "/static/hair-preview/0001/main.png"),
                new CategoryListResponse.CategoryItem("medium", "medium", "/static/hair-preview/0002/main.png"));
    }

    public List<HairCard> findCategoryCards(String categoryId) {
        if ("medium".equalsIgnoreCase(categoryId)) {
            return List.of(sampleHair(501, "medium", 1, false), sampleHair(502, "medium", 3, true));
        }
        if ("all".equalsIgnoreCase(categoryId)) {
            return List.of(sampleHair(503, "short", 1, false), sampleHair(504, "medium", 2, true));
        }
        return List.of(sampleHair(505, "short", 2, false), sampleHair(506, "short", 4, true));
    }

    public List<HairCard> findRecentCards() {
        return List.of(sampleHair(101, "short", 1, true), sampleHair(102, "medium", 2, false));
    }

    public List<HairCard> findLikeCards() {
        return List.of(sampleHair(201, "short", 1, true), sampleHair(202, "leaf", 2, true));
    }

    private HairCard sampleHair(int id, String category, int daysAgo, boolean liked) {
        String name = "sample-%d".formatted(id);
        return new HairCard(
                id,
                "/static/hairs/%d/preview.png".formatted(id),
                liked,
                "%s 추천 스타일".formatted(name),
                name,
                "%04d".formatted(id),
                category,
                OffsetDateTime.now().minusDays(daysAgo));
    }
}
