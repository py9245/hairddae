package com.example.beapp.persistence.entity;

import java.time.OffsetDateTime;

import org.hibernate.annotations.CreationTimestamp;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(
        name = "hair_likes",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_hair_likes_user_hair", columnNames = {"user_id", "hair_id"})
        }
)
public class HairLikeEntity {

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
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    protected HairLikeEntity() {
    }

    public HairLikeEntity(UserEntity user, HairEntity hair) {
        this.user = user;
        this.hair = hair;
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

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }
}
