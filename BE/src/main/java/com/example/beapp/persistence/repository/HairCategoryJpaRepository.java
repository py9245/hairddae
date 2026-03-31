package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HairCategoryEntity;

public interface HairCategoryJpaRepository extends JpaRepository<HairCategoryEntity, Long> {
    Optional<HairCategoryEntity> findByCategoryIdIgnoreCase(String categoryId);

    List<HairCategoryEntity> findAllByActiveTrueOrderByDisplayOrderAscCreatedAtAsc();

    List<HairCategoryEntity> findAllByOrderByDisplayOrderAscCreatedAtAsc();
}
