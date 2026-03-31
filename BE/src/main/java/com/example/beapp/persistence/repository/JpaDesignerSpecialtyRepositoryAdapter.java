package com.example.beapp.persistence.repository;

import java.util.List;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.DesignerSpecialty;
import com.example.beapp.persistence.entity.DesignerSpecialtyEntity;
import com.example.beapp.repository.DesignerSpecialtyRepository;

@Repository
@Primary
@Profile("!test")
public class JpaDesignerSpecialtyRepositoryAdapter implements DesignerSpecialtyRepository {

    private final DesignerSpecialtyJpaRepository designerSpecialtyJpaRepository;

    public JpaDesignerSpecialtyRepositoryAdapter(DesignerSpecialtyJpaRepository designerSpecialtyJpaRepository) {
        this.designerSpecialtyJpaRepository = designerSpecialtyJpaRepository;
    }

    @Override
    public List<DesignerSpecialty> findAllByUserId(String userId) {
        return designerSpecialtyJpaRepository.findAllByUserIdOrderByIdAsc(userId).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    public List<DesignerSpecialty> replaceAll(String userId, List<String> categoryIds) {
        designerSpecialtyJpaRepository.deleteByUserId(userId);
        designerSpecialtyJpaRepository.flush();

        if (categoryIds.isEmpty()) {
            return List.of();
        }

        return designerSpecialtyJpaRepository.saveAll(categoryIds.stream()
                        .map(categoryId -> new DesignerSpecialtyEntity(userId, categoryId))
                        .toList()).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    public List<DesignerSpecialty> saveAll(List<DesignerSpecialty> designerSpecialties) {
        return designerSpecialtyJpaRepository.saveAll(designerSpecialties.stream()
                        .map(specialty -> new DesignerSpecialtyEntity(specialty.userId(), specialty.categoryId()))
                        .toList()).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    public void deleteByUserId(String userId) {
        designerSpecialtyJpaRepository.deleteByUserId(userId);
    }

    private DesignerSpecialty toModel(DesignerSpecialtyEntity entity) {
        return new DesignerSpecialty(entity.getUserId(), entity.getCategoryId());
    }
}
