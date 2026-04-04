package com.example.beapp.repository;

import java.util.Optional;

public interface HairLookupRepository {
    Optional<HairInfo> findActiveById(Long hairId);

    record HairInfo(
            Long id,
            String categoryId
    ) {
    }
}
