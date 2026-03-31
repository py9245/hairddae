package com.example.beapp.repository;

import java.util.List;

import com.example.beapp.model.DesignerSpecialty;

public interface DesignerSpecialtyRepository {
    List<DesignerSpecialty> findAllByCategoryId(String categoryId);

    List<DesignerSpecialty> findAllByUserId(String userId);

    List<DesignerSpecialty> replaceAll(String userId, List<String> categoryIds);

    List<DesignerSpecialty> saveAll(List<DesignerSpecialty> designerSpecialties);

    void deleteByUserId(String userId);
}
