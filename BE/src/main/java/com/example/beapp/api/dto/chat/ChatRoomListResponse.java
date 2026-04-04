package com.example.beapp.api.dto.chat;

import java.time.OffsetDateTime;
import java.util.List;

import com.example.beapp.model.ChatMessageType;
import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatRoomListResponse(
        int code,
        String message,
        List<ChatRoomItem> rooms
) {
    public static ChatRoomListResponse ok(List<ChatRoomItem> rooms) {
        return new ChatRoomListResponse(200, "채팅방 조회 성공", rooms);
    }

    public record ChatRoomItem(
            @JsonProperty("room_id")
            Long roomId,
            @JsonProperty("partner_user_id")
            String partnerUserId,
            @JsonProperty("last_message_type")
            ChatMessageType lastMessageType,
            @JsonProperty("last_message_text")
            String lastMessageText,
            @JsonProperty("last_image_url")
            String lastImageUrl,
            @JsonProperty("last_message_created_at")
            OffsetDateTime lastMessageCreatedAt
    ) {
    }
}
