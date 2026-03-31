package com.example.beapp.persistence.repository;

import java.util.Optional;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.DesignerApplication;
import com.example.beapp.persistence.entity.DesignerApplicationEntity;
import com.example.beapp.repository.DesignerApplicationRepository;

@Repository
@Primary
@Profile("!test")
public class JpaDesignerApplicationRepositoryAdapter implements DesignerApplicationRepository {

    private final DesignerApplicationJpaRepository designerApplicationJpaRepository;

    public JpaDesignerApplicationRepositoryAdapter(DesignerApplicationJpaRepository designerApplicationJpaRepository) {
        this.designerApplicationJpaRepository = designerApplicationJpaRepository;
    }

    @Override
    public boolean existsByUserId(String userId) {
        return designerApplicationJpaRepository.existsByUserId(userId);
    }

    @Override
    public Optional<DesignerApplication> findByUserId(String userId) {
        return designerApplicationJpaRepository.findByUserId(userId).map(this::toModel);
    }

    @Override
    public DesignerApplication save(DesignerApplication designerApplication) {
        DesignerApplicationEntity saved = designerApplicationJpaRepository.save(
                new DesignerApplicationEntity(
                        designerApplication.userId(),
                        designerApplication.certificateNumber(),
                        designerApplication.salonAddress()));
        return toModel(saved);
    }

    @Override
    public void deleteByUserId(String userId) {
        designerApplicationJpaRepository.deleteByUserId(userId);
    }

    private DesignerApplication toModel(DesignerApplicationEntity entity) {
        return new DesignerApplication(
                entity.getUserId(),
                entity.getCertificateNumber(),
                entity.getSalonAddress());
    }
}
