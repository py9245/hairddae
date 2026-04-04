package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.repository.HairLookupRepository;

@Repository
@Primary
@Profile("!test")
public class JpaHairLookupRepositoryAdapter implements HairLookupRepository {

    private final HairJpaRepository hairJpaRepository;

    public JpaHairLookupRepositoryAdapter(HairJpaRepository hairJpaRepository) {
        this.hairJpaRepository = hairJpaRepository;
    }

    @Override
    public Optional<HairInfo> findActiveById(Long hairId) {
        return hairJpaRepository.findByIdAndActiveTrue(hairId)
                .map(hair -> new HairInfo(hair.getId(), hair.getCategoryId()));
    }
}
