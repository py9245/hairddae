package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.DesignerApplicationEntity;

public interface DesignerApplicationJpaRepository extends JpaRepository<DesignerApplicationEntity, Long> {
    boolean existsByUserId(String userId);

    Optional<DesignerApplicationEntity> findByUserId(String userId);

    void deleteByUserId(String userId);
}
