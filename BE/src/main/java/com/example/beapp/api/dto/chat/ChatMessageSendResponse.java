package com.example.beapp.api.dto.chat;

import java.time.OffsetDateTime;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatMessageSendResponse(
        int code,
        String message,
        @JsonProperty("room_id")
        Long roomId,
        @JsonProperty("message_id")
        Long messageId,
        @JsonProperty("created_at")
        OffsetDateTime createdAt
) {
    public static ChatMessageSendResponse ok(Long roomId, Long messageId, OffsetDateTime createdAt) {
        return new ChatMessageSendResponse(200, "메시지 전송 성공", roomId, messageId, createdAt);
    }
}
