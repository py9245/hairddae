package com.example.beapp.repository;

import java.util.List;

import com.example.beapp.model.DesignerSpecialty;

public interface DesignerSpecialtyRepository {
    List<DesignerSpecialty> findAllByUserId(String userId);

    List<DesignerSpecialty> saveAll(List<DesignerSpecialty> designerSpecialties);

    void deleteByUserId(String userId);
}
