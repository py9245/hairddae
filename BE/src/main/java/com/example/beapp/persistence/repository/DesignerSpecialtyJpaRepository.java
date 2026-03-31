package com.example.beapp.persistence.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.DesignerSpecialtyEntity;

public interface DesignerSpecialtyJpaRepository extends JpaRepository<DesignerSpecialtyEntity, Long> {
    List<DesignerSpecialtyEntity> findAllByUserIdOrderByIdAsc(String userId);

    void deleteByUserId(String userId);
}
