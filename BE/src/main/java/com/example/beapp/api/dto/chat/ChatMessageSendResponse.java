package com.example.beapp.api.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatMessageSendResponse(
        int code,
        String message,
        @JsonProperty("room_id")
        Long roomId,
        @JsonProperty("message_id")
        Long messageId
) {
    public static ChatMessageSendResponse ok(Long roomId, Long messageId) {
        return new ChatMessageSendResponse(200, "메시지 전송 성공", roomId, messageId);
    }
}
