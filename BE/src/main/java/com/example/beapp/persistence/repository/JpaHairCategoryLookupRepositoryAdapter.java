package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.repository.HairCategoryLookupRepository;

@Repository
@Primary
@Profile("!test")
public class JpaHairCategoryLookupRepositoryAdapter implements HairCategoryLookupRepository {

    private final HairCategoryJpaRepository hairCategoryJpaRepository;

    public JpaHairCategoryLookupRepositoryAdapter(HairCategoryJpaRepository hairCategoryJpaRepository) {
        this.hairCategoryJpaRepository = hairCategoryJpaRepository;
    }

    @Override
    public Optional<HairCategoryInfo> findByCategoryId(String categoryId) {
        return hairCategoryJpaRepository.findByCategoryIdIgnoreCase(categoryId)
                .map(category -> new HairCategoryInfo(category.getCategoryId(), category.getCategoryName()));
    }
}
