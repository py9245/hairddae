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

    @Column(name = "slug", length = 120)
    private String slug;

    @Column(name = "category", nullable = false, length = 50)
    private String category;

    @Column(name = "dataset_code", length = 50)
    private String datasetCode;

    @Column(name = "dataset_root_url", length = 500)
    private String datasetRootUrl;

    @Column(name = "asset_index_url", length = 500)
    private String assetIndexUrl;

    @Column(name = "representative_asset_id", length = 255)
    private String representativeAssetId;

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

    public void applyCatalogMetadata(
            String name,
            String slug,
            String category,
            String datasetCode,
            String previewImageUrl,
            String description,
            boolean active
    ) {
        this.name = name;
        this.slug = slug;
        this.category = category;
        this.datasetCode = datasetCode;
        this.datasetRootUrl = null;
        this.assetIndexUrl = null;
        this.representativeAssetId = null;
        this.previewImageUrl = previewImageUrl;
        this.description = description;
        this.active = active;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getSlug() {
        return slug;
    }

    public String getCategory() {
        return category;
    }

    public String getDatasetCode() {
        return datasetCode;
    }

    public String getDatasetRootUrl() {
        return datasetRootUrl;
    }

    public String getAssetIndexUrl() {
        return assetIndexUrl;
    }

    public String getRepresentativeAssetId() {
        return representativeAssetId;
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

    public void incrementLikeCount() {
        likeCount = likeCount == null ? 1 : likeCount + 1;
    }

    public void decrementLikeCount() {
        if (likeCount == null || likeCount <= 0) {
            likeCount = 0;
            return;
        }
        likeCount -= 1;
    }

    public void incrementViewCount() {
        viewCount = viewCount == null ? 1 : viewCount + 1;
    }
}
