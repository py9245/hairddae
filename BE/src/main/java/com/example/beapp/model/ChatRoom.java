package com.example.beapp.model;

import java.time.OffsetDateTime;

public record ChatRoom(
        Long id,
        String customerUserId,
        String designerUserId,
        Long sourceHairId,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt
) {
    public ChatRoom(String customerUserId, String designerUserId, Long sourceHairId) {
        this(null, customerUserId, designerUserId, sourceHairId, null, null);
    }

    public ChatRoom withSourceHairId(Long sourceHairId) {
        return new ChatRoom(id, customerUserId, designerUserId, sourceHairId, createdAt, updatedAt);
    }

    public boolean hasParticipant(String userId) {
        return customerUserId.equals(userId) || designerUserId.equals(userId);
    }

    public String partnerUserId(String currentUserId) {
        return customerUserId.equals(currentUserId) ? designerUserId : customerUserId;
    }
}
