package com.example.beapp.repository;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.DesignerSpecialty;

@Repository
@Profile("test")
public class InMemoryDesignerSpecialtyRepository implements DesignerSpecialtyRepository {

    private final Map<String, LinkedHashMap<String, DesignerSpecialty>> storage = new ConcurrentHashMap<>();

    @Override
    public List<DesignerSpecialty> findAllByUserId(String userId) {
        LinkedHashMap<String, DesignerSpecialty> specialties = storage.get(userId);
        if (specialties == null) {
            return List.of();
        }
        return new ArrayList<>(specialties.values());
    }

    @Override
    public List<DesignerSpecialty> saveAll(List<DesignerSpecialty> designerSpecialties) {
        if (designerSpecialties.isEmpty()) {
            return List.of();
        }
        String userId = designerSpecialties.get(0).userId();
        LinkedHashMap<String, DesignerSpecialty> specialties = storage.computeIfAbsent(userId, key -> new LinkedHashMap<>());
        for (DesignerSpecialty specialty : designerSpecialties) {
            specialties.put(specialty.categoryId(), specialty);
        }
        return new ArrayList<>(specialties.values());
    }

    @Override
    public void deleteByUserId(String userId) {
        storage.remove(userId);
    }
}
