package com.example.beapp.persistence.entity;

import java.time.OffsetDateTime;

import org.hibernate.annotations.CreationTimestamp;

import com.example.beapp.model.ChatMessageType;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "chat_messages")
public class ChatMessageEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "room_id", nullable = false)
    private Long roomId;

    @Column(name = "sender_user_id", nullable = false, length = 50)
    private String senderUserId;

    @Enumerated(EnumType.STRING)
    @Column(name = "message_type", nullable = false, length = 20)
    private ChatMessageType messageType;

    @Column(name = "message_text", columnDefinition = "text")
    private String messageText;

    @Column(name = "image_url", length = 500)
    private String imageUrl;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "read_at")
    private OffsetDateTime readAt;

    protected ChatMessageEntity() {
    }

    public ChatMessageEntity(
            Long roomId,
            String senderUserId,
            ChatMessageType messageType,
            String messageText,
            String imageUrl) {
        this.roomId = roomId;
        this.senderUserId = senderUserId;
        this.messageType = messageType;
        this.messageText = messageText;
        this.imageUrl = imageUrl;
    }

    public Long getId() {
        return id;
    }

    public Long getRoomId() {
        return roomId;
    }

    public String getSenderUserId() {
        return senderUserId;
    }

    public ChatMessageType getMessageType() {
        return messageType;
    }

    public String getMessageText() {
        return messageText;
    }

    public String getImageUrl() {
        return imageUrl;
    }

    public OffsetDateTime getCreatedAt() {
        return createdAt;
    }

    public OffsetDateTime getReadAt() {
        return readAt;
    }
}
