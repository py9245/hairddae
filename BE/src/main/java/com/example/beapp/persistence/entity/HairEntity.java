package com.example.beapp.persistence.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

@Entity
@Table(
        name = "hairs",
        indexes = {
                @Index(name = "idx_hairs_category_active", columnList = "category,is_active")
        }
)
public class HairEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "name", nullable = false, length = 120)
    private String name;

    @Column(name = "category", nullable = false, length = 50)
    private String category;

    @Column(name = "preview_image_url", length = 500)
    private String previewImageUrl;

    @Column(name = "description", columnDefinition = "text")
    private String description;

    @Column(name = "like_count", nullable = false)
    private Integer likeCount = 0;

    @Column(name = "view_count", nullable = false)
    private Integer viewCount = 0;

    @Column(name = "is_active", nullable = false)
    private Boolean active = Boolean.TRUE;

    protected HairEntity() {
    }

    public HairEntity(String name, String category, String previewImageUrl, String description) {
        this.name = name;
        this.category = category;
        this.previewImageUrl = previewImageUrl;
        this.description = description;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getCategory() {
        return category;
    }

    public String getPreviewImageUrl() {
        return previewImageUrl;
    }

    public String getDescription() {
        return description;
    }

    public Integer getLikeCount() {
        return likeCount;
    }

    public Integer getViewCount() {
        return viewCount;
    }

    public Boolean getActive() {
        return active;
    }
}
