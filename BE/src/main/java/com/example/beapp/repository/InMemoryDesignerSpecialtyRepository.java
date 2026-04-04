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
    public List<DesignerSpecialty> findAllByCategoryId(String categoryId) {
        return storage.values().stream()
                .flatMap(specialties -> specialties.values().stream())
                .filter(specialty -> specialty.categoryId().equalsIgnoreCase(categoryId))
                .toList();
    }

    @Override
    public List<DesignerSpecialty> findAllByUserId(String userId) {
        LinkedHashMap<String, DesignerSpecialty> specialties = storage.get(userId);
        if (specialties == null) {
            return List.of();
        }
        return new ArrayList<>(specialties.values());
    }

    @Override
    public List<DesignerSpecialty> replaceAll(String userId, List<String> categoryIds) {
        deleteByUserId(userId);
        List<DesignerSpecialty> specialties = categoryIds.stream()
                .map(categoryId -> new DesignerSpecialty(userId, categoryId))
                .toList();
        return saveAll(specialties);
    }

    @Override
    public List<DesignerSpecialty> saveAll(List<DesignerSpecialty> designerSpecialties) {
        if (designerSpecialties.isEmpty()) {
            return List.of();
        }
        for (DesignerSpecialty specialty : designerSpecialties) {
            LinkedHashMap<String, DesignerSpecialty> specialties = storage.computeIfAbsent(
                    specialty.userId(),
                    key -> new LinkedHashMap<>());
            specialties.put(specialty.categoryId(), specialty);
        }
        return designerSpecialties.stream()
                .map(DesignerSpecialty::userId)
                .distinct()
                .flatMap(userId -> storage.getOrDefault(userId, new LinkedHashMap<>()).values().stream())
                .toList();
    }

    @Override
    public void deleteByUserId(String userId) {
        storage.remove(userId);
    }
}
