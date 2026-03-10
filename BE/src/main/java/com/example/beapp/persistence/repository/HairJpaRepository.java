package com.example.beapp.persistence.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HairEntity;

public interface HairJpaRepository extends JpaRepository<HairEntity, Long> {
}
