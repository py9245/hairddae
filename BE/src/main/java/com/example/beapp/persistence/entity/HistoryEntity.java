package com.example.beapp.persistence.entity;

import java.time.OffsetDateTime;

import org.hibernate.annotations.CreationTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(
        name = "histories",
        indexes = {
                @Index(name = "idx_histories_user_viewed_at", columnList = "user_id,viewed_at")
        }
)
public class HistoryEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "user_id", nullable = false)
    private UserEntity user;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "hair_id", nullable = false)
    private HairEntity hair;

    @CreationTimestamp
    @Column(name = "viewed_at", nullable = false, updatable = false)
    private OffsetDateTime viewedAt;

    @Column(name = "view_seconds", nullable = false)
    private Integer viewSeconds = 0;

    protected HistoryEntity() {
    }

    public HistoryEntity(UserEntity user, HairEntity hair, Integer viewSeconds) {
        this.user = user;
        this.hair = hair;
        this.viewSeconds = viewSeconds;
    }

    public Long getId() {
        return id;
    }

    public UserEntity getUser() {
        return user;
    }

    public HairEntity getHair() {
        return hair;
    }

    public OffsetDateTime getViewedAt() {
        return viewedAt;
    }

    public Integer getViewSeconds() {
        return viewSeconds;
    }
}
