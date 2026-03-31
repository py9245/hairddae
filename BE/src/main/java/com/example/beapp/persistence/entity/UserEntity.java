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
                @UniqueConstraint(name = "uq_users_user_id", columnNames = "user_id"),
                @UniqueConstraint(name = "uq_users_provider_subject", columnNames = "provider_subject")
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

    @Column(name = "login_type", nullable = false)
    private short loginType;

    @Column(name = "provider_subject", length = 255)
    private String providerSubject;

    @Column(name = "grade", nullable = false)
    private short grade;

    protected UserEntity() {
    }

    public UserEntity(String userId, String passwordHash, LocalDate birthDate, String gender) {
        this(userId, passwordHash, birthDate, gender, (short) 0, null, (short) 0);
    }

    public UserEntity(String userId, String passwordHash, LocalDate birthDate, String gender, short loginType) {
        this(userId, passwordHash, birthDate, gender, loginType, null, (short) 0);
    }

    public UserEntity(
            String userId,
            String passwordHash,
            LocalDate birthDate,
            String gender,
            short loginType,
            String providerSubject) {
        this(userId, passwordHash, birthDate, gender, loginType, providerSubject, (short) 0);
    }

    public UserEntity(
            String userId,
            String passwordHash,
            LocalDate birthDate,
            String gender,
            short loginType,
            String providerSubject,
            short grade) {
        this.userId = userId;
        this.passwordHash = passwordHash;
        this.birthDate = birthDate;
        this.gender = gender;
        this.loginType = loginType;
        this.providerSubject = providerSubject;
        this.grade = grade;
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

    public short getLoginType() {
        return loginType;
    }

    public String getProviderSubject() {
        return providerSubject;
    }

    public short getGrade() {
        return grade;
    }

    public UserEntity update(
            String userId,
            String passwordHash,
            LocalDate birthDate,
            String gender,
            short loginType,
            String providerSubject,
            short grade) {
        this.userId = userId;
        this.passwordHash = passwordHash;
        this.birthDate = birthDate;
        this.gender = gender;
        this.loginType = loginType;
        this.providerSubject = providerSubject;
        this.grade = grade;
        return this;
    }
}
