package com.example.beapp.persistence.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HairLikeEntity;

public interface HairLikeJpaRepository extends JpaRepository<HairLikeEntity, Long> {
}
