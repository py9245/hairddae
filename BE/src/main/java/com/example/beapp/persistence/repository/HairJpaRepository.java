package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HairEntity;

public interface HairJpaRepository extends JpaRepository<HairEntity, Long> {
    Optional<HairEntity> findByDatasetCode(String datasetCode);

    Optional<HairEntity> findBySlug(String slug);

    Optional<HairEntity> findByIdAndActiveTrue(Long id);

    List<HairEntity> findByActiveTrue(Sort sort);

    List<HairEntity> findByActiveTrueAndCategoryIgnoreCase(String category, Sort sort);

    List<HairEntity> findByActiveTrueAndCategoryIdIgnoreCase(String categoryId, Sort sort);

    Page<HairEntity> findByActiveTrue(Pageable pageable);

    Page<HairEntity> findByActiveTrueAndCategoryIgnoreCase(String category, Pageable pageable);

    Page<HairEntity> findByActiveTrueAndCategoryIdIgnoreCase(String categoryId, Pageable pageable);
}
