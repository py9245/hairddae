package com.example.beapp.repository;

import java.util.Optional;

import com.example.beapp.model.DesignerApplication;

public interface DesignerApplicationRepository {
    boolean existsByUserId(String userId);

    Optional<DesignerApplication> findByUserId(String userId);

    DesignerApplication save(DesignerApplication designerApplication);

    void deleteByUserId(String userId);
}
