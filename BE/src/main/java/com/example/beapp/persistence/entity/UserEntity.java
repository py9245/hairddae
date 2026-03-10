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

    @Column(name = "age")
    private Short age;

    @Column(name = "gender", length = 1)
    private String gender;

    protected UserEntity() {
    }

    public UserEntity(String userId, String passwordHash, Short age, String gender) {
        this.userId = userId;
        this.passwordHash = passwordHash;
        this.age = age;
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

    public Short getAge() {
        return age;
    }

    public String getGender() {
        return gender;
    }
}
