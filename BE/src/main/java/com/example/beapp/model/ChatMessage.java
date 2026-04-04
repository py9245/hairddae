package com.example.beapp.model;

import java.time.OffsetDateTime;

public record ChatMessage(
        Long id,
        Long roomId,
        String senderUserId,
        ChatMessageType messageType,
        String messageText,
        String imageUrl,
        OffsetDateTime createdAt,
        OffsetDateTime readAt
) {
    public static ChatMessage text(Long roomId, String senderUserId, String messageText) {
        return new ChatMessage(null, roomId, senderUserId, ChatMessageType.TEXT, messageText, null, null, null);
    }

    public static ChatMessage image(Long roomId, String senderUserId, String imageUrl) {
        return new ChatMessage(null, roomId, senderUserId, ChatMessageType.IMAGE, null, imageUrl, null, null);
    }
}
