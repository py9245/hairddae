package com.example.beapp.persistence.repository;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.HistoryEntity;

public interface HistoryJpaRepository extends JpaRepository<HistoryEntity, Long> {
}
