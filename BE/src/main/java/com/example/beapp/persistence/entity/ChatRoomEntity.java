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
        name = "chat_rooms",
        uniqueConstraints = {
                @UniqueConstraint(name = "uq_chat_rooms_customer_designer", columnNames = {"customer_user_id", "designer_user_id"})
        }
)
public class ChatRoomEntity extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "customer_user_id", nullable = false, length = 50)
    private String customerUserId;

    @Column(name = "designer_user_id", nullable = false, length = 50)
    private String designerUserId;

    @Column(name = "source_hair_id")
    private Long sourceHairId;

    protected ChatRoomEntity() {
    }

    public ChatRoomEntity(String customerUserId, String designerUserId, Long sourceHairId) {
        this.customerUserId = customerUserId;
        this.designerUserId = designerUserId;
        this.sourceHairId = sourceHairId;
    }

    public ChatRoomEntity update(String customerUserId, String designerUserId, Long sourceHairId) {
        this.customerUserId = customerUserId;
        this.designerUserId = designerUserId;
        this.sourceHairId = sourceHairId;
        return this;
    }

    public Long getId() {
        return id;
    }

    public String getCustomerUserId() {
        return customerUserId;
    }

    public String getDesignerUserId() {
        return designerUserId;
    }

    public Long getSourceHairId() {
        return sourceHairId;
    }
}
