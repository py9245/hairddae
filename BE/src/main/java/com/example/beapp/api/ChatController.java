package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.chat.ChatMessageListResponse;
import com.example.beapp.api.dto.chat.ChatMessageSendRequest;
import com.example.beapp.api.dto.chat.ChatMessageSendResponse;
import com.example.beapp.api.dto.chat.ChatRoomCreateResponse;
import com.example.beapp.api.dto.chat.ChatRoomListResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.service.ChatService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;

@RestController
@Validated
@RequestMapping("/api/chat/rooms")
public class ChatController {

    private final ChatService chatService;

    public ChatController(ChatService chatService) {
        this.chatService = chatService;
    }

    @PostMapping(path = {"", "/"}, consumes = {"multipart/form-data"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<ChatRoomCreateResponse> createRoom(
            Authentication authentication,
            @RequestParam("designer_user_id")
            @NotBlank(message = "designer_user_id는 필수입니다.")
            @Size(max = 50, message = "designer_user_id는 50자 이하여야 합니다.")
            String designerUserId,
            @RequestParam("hair_id")
            @NotNull(message = "hair_id는 필수입니다.")
            @Positive(message = "hair_id는 1 이상이어야 합니다.")
            Long hairId,
            @RequestPart("applied_image") MultipartFile appliedImage,
            @RequestParam(value = "initial_message", required = false)
            @Size(max = 1000, message = "initial_message는 1000자 이하여야 합니다.")
            String initialMessage) {
        return ResponseEntity.ok(chatService.createRoom(
                getAuthenticatedUserId(authentication),
                designerUserId,
                hairId,
                appliedImage,
                initialMessage));
    }

    @GetMapping(path = {"", "/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<ChatRoomListResponse> getRooms(Authentication authentication) {
        return ResponseEntity.ok(chatService.getRooms(getAuthenticatedUserId(authentication)));
    }

    @GetMapping(path = {"/{roomId}/messages", "/{roomId}/messages/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<ChatMessageListResponse> getMessages(
            Authentication authentication,
            @PathVariable("roomId") Long roomId,
            @RequestParam(value = "after_id", required = false) Long afterId) {
        return ResponseEntity.ok(chatService.getMessages(getAuthenticatedUserId(authentication), roomId, afterId));
    }

    @PostMapping(path = {"/{roomId}/messages", "/{roomId}/messages/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<ChatMessageSendResponse> sendMessage(
            Authentication authentication,
            @PathVariable("roomId") Long roomId,
            @Valid @RequestBody ChatMessageSendRequest request) {
        return ResponseEntity.ok(chatService.sendMessage(getAuthenticatedUserId(authentication), roomId, request));
    }

    private String getAuthenticatedUserId(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return authentication.getName();
    }
}
