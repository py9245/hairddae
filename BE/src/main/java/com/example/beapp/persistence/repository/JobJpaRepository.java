package com.example.beapp.persistence.repository;

import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.JobEntity;

public interface JobJpaRepository extends JpaRepository<JobEntity, UUID> {
}
