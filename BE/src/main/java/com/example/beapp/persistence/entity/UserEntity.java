package com.example.beapp.persistence.entity;

import java.time.LocalDate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

@Entity
@Table(
        name = "users",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_users_user_id", columnNames = "user_id")
        }
)
public class UserEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(name = "birth_date")
    private LocalDate birthDate;

    @Column(name = "gender", length = 1)
    private String gender;

    protected UserEntity() {
    }

    public UserEntity(String userId, String passwordHash, LocalDate birthDate, String gender) {
        this.userId = userId;
        this.passwordHash = passwordHash;
        this.birthDate = birthDate;
        this.gender = gender;
    }

    public Long getId() {
        return id;
    }

    public String getUserId() {
        return userId;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public LocalDate getBirthDate() {
        return birthDate;
    }

    public String getGender() {
        return gender;
    }

    public UserEntity update(String passwordHash, LocalDate birthDate, String gender) {
        this.passwordHash = passwordHash;
        this.birthDate = birthDate;
        this.gender = gender;
        return this;
    }
}
