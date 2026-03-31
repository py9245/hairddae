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
        name = "designer_applications",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_designer_applications_user_id", columnNames = "user_id")
        }
)
public class DesignerApplicationEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(name = "certificate_number", nullable = false, length = 255)
    private String certificateNumber;

    @Column(name = "salon_address", nullable = false, length = 500)
    private String salonAddress;

    @Column(name = "salon_latitude")
    private Double salonLatitude;

    @Column(name = "salon_longitude")
    private Double salonLongitude;

    protected DesignerApplicationEntity() {
    }

    public DesignerApplicationEntity(String userId, String certificateNumber, String salonAddress) {
        this(userId, certificateNumber, salonAddress, null, null);
    }

    public DesignerApplicationEntity(
            String userId,
            String certificateNumber,
            String salonAddress,
            Double salonLatitude,
            Double salonLongitude) {
        this.userId = userId;
        this.certificateNumber = certificateNumber;
        this.salonAddress = salonAddress;
        this.salonLatitude = salonLatitude;
        this.salonLongitude = salonLongitude;
    }

    public String getUserId() {
        return userId;
    }

    public String getCertificateNumber() {
        return certificateNumber;
    }

    public String getSalonAddress() {
        return salonAddress;
    }

    public Double getSalonLatitude() {
        return salonLatitude;
    }

    public Double getSalonLongitude() {
        return salonLongitude;
    }
}
