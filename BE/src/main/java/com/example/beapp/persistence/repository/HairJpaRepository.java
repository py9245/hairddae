package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HairEntity;

public interface HairJpaRepository extends JpaRepository<HairEntity, Long> {
    Optional<HairEntity> findByDatasetCode(String datasetCode);

    Optional<HairEntity> findBySlug(String slug);

    Optional<HairEntity> findByIdAndActiveTrue(Long id);

    Page<HairEntity> findByActiveTrue(Pageable pageable);

    Page<HairEntity> findByActiveTrueAndCategoryIgnoreCase(String category, Pageable pageable);
}
