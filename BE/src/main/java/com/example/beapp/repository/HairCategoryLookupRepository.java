package com.example.beapp.repository;

import java.util.Optional;

public interface HairCategoryLookupRepository {
    Optional<HairCategoryInfo> findByCategoryId(String categoryId);

    record HairCategoryInfo(
            String categoryId,
            String categoryName
    ) {
    }
}
