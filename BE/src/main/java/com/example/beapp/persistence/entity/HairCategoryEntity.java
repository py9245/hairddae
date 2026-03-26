package com.example.beapp.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(
        name = "hair_categories",
        indexes = {
                @Index(name = "idx_hair_categories_active_order", columnList = "is_active,display_order,created_at")
        },
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_hair_categories_category_id", columnNames = "category_id")
        }
)
public class HairCategoryEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "category_id", nullable = false, length = 50)
    private String categoryId;

    @Column(name = "category_name", nullable = false, length = 120)
    private String categoryName;

    @Column(name = "preview_image_url", length = 500)
    private String previewImageUrl;

    @Column(name = "description", columnDefinition = "text")
    private String description;

    @Column(name = "display_order", nullable = false)
    private Integer displayOrder = 0;

    @Column(name = "is_active", nullable = false)
    private Boolean active = Boolean.TRUE;

    protected HairCategoryEntity() {
    }

    public HairCategoryEntity(String categoryId, String categoryName, String previewImageUrl, String description) {
        this.categoryId = categoryId;
        this.categoryName = categoryName;
        this.previewImageUrl = previewImageUrl;
        this.description = description;
    }

    public void applyMetadata(
            String categoryId,
            String categoryName,
            String previewImageUrl,
            String description,
            int displayOrder,
            boolean active
    ) {
        this.categoryId = categoryId;
        this.categoryName = categoryName;
        this.previewImageUrl = previewImageUrl;
        this.description = description;
        this.displayOrder = displayOrder;
        this.active = active;
    }

    public Long getId() {
        return id;
    }

    public String getCategoryId() {
        return categoryId;
    }

    public String getCategoryName() {
        return categoryName;
    }

    public String getPreviewImageUrl() {
        return previewImageUrl;
    }

    public String getDescription() {
        return description;
    }

    public Integer getDisplayOrder() {
        return displayOrder;
    }

    public Boolean getActive() {
        return active;
    }
}
