package com.example.beapp.api.dto.chat;

import java.time.OffsetDateTime;
import java.util.List;

import com.example.beapp.model.ChatMessageType;
import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatMessageListResponse(
        int code,
        String message,
        @JsonProperty("room_id")
        Long roomId,
        List<ChatMessageItem> messages
) {
    public static ChatMessageListResponse ok(Long roomId, List<ChatMessageItem> messages) {
        return new ChatMessageListResponse(200, "메시지 조회 성공", roomId, messages);
    }

    public record ChatMessageItem(
            Long id,
            @JsonProperty("sender_user_id")
            String senderUserId,
            @JsonProperty("message_type")
            ChatMessageType messageType,
            @JsonProperty("message_text")
            String messageText,
            @JsonProperty("image_url")
            String imageUrl,
            @JsonProperty("created_at")
            OffsetDateTime createdAt,
            boolean mine
    ) {
    }
}
