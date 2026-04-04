package com.example.beapp.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(
        name = "designer_specialties",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_designer_specialties_user_category", columnNames = {"user_id", "category_id"})
        }
)
public class DesignerSpecialtyEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(name = "category_id", nullable = false, length = 50)
    private String categoryId;

    protected DesignerSpecialtyEntity() {
    }

    public DesignerSpecialtyEntity(String userId, String categoryId) {
        this.userId = userId;
        this.categoryId = categoryId;
    }

    public String getUserId() {
        return userId;
    }

    public String getCategoryId() {
        return categoryId;
    }
}
