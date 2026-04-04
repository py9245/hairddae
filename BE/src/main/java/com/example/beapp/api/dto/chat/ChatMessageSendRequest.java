package com.example.beapp.api.dto.chat;

import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChatMessageSendRequest(
        @JsonProperty("message_text")
        @NotBlank(message = "message_text는 필수입니다.")
        @Size(max = 1000, message = "message_text는 1000자 이하여야 합니다.")
        String messageText
) {
}
