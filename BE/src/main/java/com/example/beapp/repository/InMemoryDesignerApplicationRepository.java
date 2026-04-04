package com.example.beapp.repository;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.DesignerApplication;

@Repository
@Profile("test")
public class InMemoryDesignerApplicationRepository implements DesignerApplicationRepository {

    private final Map<String, DesignerApplication> applications = new ConcurrentHashMap<>();

    @Override
    public boolean existsByUserId(String userId) {
        return applications.containsKey(userId);
    }

    @Override
    public Optional<DesignerApplication> findByUserId(String userId) {
        return Optional.ofNullable(applications.get(userId));
    }

    @Override
    public DesignerApplication save(DesignerApplication designerApplication) {
        applications.put(designerApplication.userId(), designerApplication);
        return designerApplication;
    }

    @Override
    public void deleteByUserId(String userId) {
        applications.remove(userId);
    }
}
