package com.example.beapp.api.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;

public record ChatRoomCreateResponse(
        int code,
        String message,
        @JsonProperty("room_id")
        Long roomId,
        @JsonProperty("designer_user_id")
        String designerUserId,
        @JsonProperty("initial_image_url")
        String initialImageUrl
) {
    public static ChatRoomCreateResponse ok(Long roomId, String designerUserId, String initialImageUrl) {
        return new ChatRoomCreateResponse(200, "채팅방 연결 성공", roomId, designerUserId, initialImageUrl);
    }
}
