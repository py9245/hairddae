package com.example.beapp.persistence.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.AdEntity;

public interface AdJpaRepository extends JpaRepository<AdEntity, Long> {
}
