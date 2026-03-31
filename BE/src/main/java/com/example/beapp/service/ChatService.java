package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.OffsetDateTime;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.chat.ChatMessageListResponse;
import com.example.beapp.api.dto.chat.ChatMessageSendRequest;
import com.example.beapp.api.dto.chat.ChatMessageSendResponse;
import com.example.beapp.api.dto.chat.ChatRoomCreateResponse;
import com.example.beapp.api.dto.chat.ChatRoomListResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppChatProperties;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.model.ChatMessage;
import com.example.beapp.model.ChatMessageType;
import com.example.beapp.model.ChatRoom;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.ChatMessageRepository;
import com.example.beapp.repository.ChatRoomRepository;
import com.example.beapp.repository.HairLookupRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class ChatService {

    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/webp");

    private final UserAccountRepository userAccountRepository;
    private final HairLookupRepository hairLookupRepository;
    private final ChatRoomRepository chatRoomRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final AppHairProperties appHairProperties;
    private final AppChatProperties appChatProperties;

    public ChatService(
            UserAccountRepository userAccountRepository,
            HairLookupRepository hairLookupRepository,
            ChatRoomRepository chatRoomRepository,
            ChatMessageRepository chatMessageRepository,
            AppHairProperties appHairProperties,
            AppChatProperties appChatProperties) {
        this.userAccountRepository = userAccountRepository;
        this.hairLookupRepository = hairLookupRepository;
        this.chatRoomRepository = chatRoomRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.appHairProperties = appHairProperties;
        this.appChatProperties = appChatProperties;
    }

    @Transactional
    public ChatRoomCreateResponse createRoom(
            String requesterUserId,
            String designerUserId,
            Long hairId,
            MultipartFile appliedImage,
            String initialMessage) {
        UserAccount requester = getRequiredUser(requesterUserId);
        UserAccount designer = getRequiredUser(designerUserId);
        verifyDesignerTarget(requester.userID(), designer);
        hairLookupRepository.findActiveById(hairId).orElseThrow(() -> new ApiException(ErrorCode.HAIR_NOT_FOUND));
        validateAppliedImage(appliedImage);

        ChatRoom room = chatRoomRepository.findByParticipants(requester.userID(), designer.userID())
                .map(existing -> Objects.equals(existing.sourceHairId(), hairId)
                        ? existing
                        : chatRoomRepository.save(existing.withSourceHairId(hairId)))
                .orElseGet(() -> chatRoomRepository.save(new ChatRoom(requester.userID(), designer.userID(), hairId)));

        String imageUrl = storeAppliedImage(room.id(), appliedImage);
        chatMessageRepository.save(ChatMessage.image(room.id(), requester.userID(), imageUrl));

        String normalizedInitialMessage = normalizeOptionalText(initialMessage);
        if (normalizedInitialMessage != null) {
            chatMessageRepository.save(ChatMessage.text(room.id(), requester.userID(), normalizedInitialMessage));
        }

        return ChatRoomCreateResponse.ok(room.id(), designer.userID(), imageUrl);
    }

    @Transactional(readOnly = true)
    public ChatRoomListResponse getRooms(String requesterUserId) {
        getRequiredUser(requesterUserId);

        List<ChatRoomListResponse.ChatRoomItem> rooms = chatRoomRepository.findAllByParticipant(requesterUserId).stream()
                .map(room -> toRoomItem(requesterUserId, room))
                .sorted(Comparator
                        .comparing(ChatRoomListResponse.ChatRoomItem::lastMessageCreatedAt, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(ChatRoomListResponse.ChatRoomItem::roomId, Comparator.reverseOrder()))
                .toList();

        return ChatRoomListResponse.ok(rooms);
    }

    @Transactional(readOnly = true)
    public ChatMessageListResponse getMessages(String requesterUserId, Long roomId, Long afterId) {
        ChatRoom room = getAuthorizedRoom(requesterUserId, roomId);

        List<ChatMessageListResponse.ChatMessageItem> messages = (afterId == null
                ? chatMessageRepository.findAllByRoomId(room.id())
                : chatMessageRepository.findAllByRoomIdAfterId(room.id(), afterId)).stream()
                .map(message -> toMessageItem(requesterUserId, message))
                .toList();

        return ChatMessageListResponse.ok(room.id(), messages);
    }

    @Transactional
    public ChatMessageSendResponse sendMessage(String requesterUserId, Long roomId, ChatMessageSendRequest request) {
        ChatRoom room = getAuthorizedRoom(requesterUserId, roomId);
        String normalizedMessageText = normalizeRequiredText(request.messageText());
        ChatMessage saved = chatMessageRepository.save(ChatMessage.text(room.id(), requesterUserId, normalizedMessageText));
        return ChatMessageSendResponse.ok(room.id(), saved.id());
    }

    private ChatRoom getAuthorizedRoom(String requesterUserId, Long roomId) {
        ChatRoom room = chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new ApiException(ErrorCode.CHAT_ROOM_NOT_FOUND));
        if (!room.hasParticipant(requesterUserId)) {
            throw new ApiException(ErrorCode.CHAT_ROOM_FORBIDDEN);
        }
        return room;
    }

    private ChatRoomListResponse.ChatRoomItem toRoomItem(String requesterUserId, ChatRoom room) {
        String partnerUserId = room.partnerUserId(requesterUserId);
        java.util.Optional<ChatMessage> latestMessage = chatMessageRepository.findLatestByRoomId(room.id());
        return new ChatRoomListResponse.ChatRoomItem(
                room.id(),
                partnerUserId,
                latestMessage.map(ChatMessage::messageType).orElse(null),
                latestMessage.map(ChatMessage::messageText).orElse(null),
                latestMessage.map(ChatMessage::imageUrl).orElse(null),
                latestMessage.map(ChatMessage::createdAt).orElse(null));
    }

    private ChatMessageListResponse.ChatMessageItem toMessageItem(String requesterUserId, ChatMessage message) {
        return new ChatMessageListResponse.ChatMessageItem(
                message.id(),
                message.senderUserId(),
                message.messageType(),
                message.messageText(),
                message.imageUrl(),
                message.createdAt(),
                message.senderUserId().equals(requesterUserId));
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private void verifyDesignerTarget(String requesterUserId, UserAccount designer) {
        if (requesterUserId.equals(designer.userID())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "자기 자신과 채팅방을 만들 수 없습니다.");
        }
        if (designer.grade() != 2) {
            throw new ApiException(ErrorCode.CHAT_TARGET_NOT_DESIGNER);
        }
    }

    private void validateAppliedImage(MultipartFile appliedImage) {
        if (appliedImage == null || appliedImage.isEmpty()) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "applied_image 파일이 필요합니다.");
        }
        if (appliedImage.getSize() > appChatProperties.maxUploadSizeBytes()) {
            throw new ApiException(ErrorCode.FILE_TOO_LARGE);
        }
        if (!StringUtils.hasText(appliedImage.getContentType())
                || !ALLOWED_CONTENT_TYPES.contains(appliedImage.getContentType().toLowerCase(Locale.ROOT))) {
            throw new ApiException(ErrorCode.UNSUPPORTED_IMAGE_TYPE);
        }
    }

    private String storeAppliedImage(Long roomId, MultipartFile appliedImage) {
        String extension = resolveFileExtension(appliedImage.getContentType());
        String fileName = UUID.randomUUID() + "." + extension;
        String relativePath = normalizeRelativePath(resolveStorageDirName() + "/rooms/" + roomId + "/messages/" + fileName);
        Path absolutePath = appHairProperties.staticRootPath().resolve(relativePath).normalize();

        try {
            Files.createDirectories(absolutePath.getParent());
            Files.write(absolutePath, appliedImage.getBytes());
        } catch (IOException exception) {
            throw new IllegalStateException("채팅 이미지를 저장하지 못했습니다: " + absolutePath, exception);
        }

        return toStaticUrl(relativePath);
    }

    private String resolveStorageDirName() {
        String configuredValue = StringUtils.hasText(appChatProperties.storageDir())
                ? appChatProperties.storageDir().trim()
                : "chat";
        String normalizedValue = normalizeRelativePath(configuredValue);
        if (!StringUtils.hasText(normalizedValue) || normalizedValue.startsWith("..")) {
            throw new IllegalStateException("chat 저장 디렉터리 설정이 올바르지 않습니다.");
        }
        return normalizedValue;
    }

    private String toStaticUrl(String relativePath) {
        String baseUrl = appHairProperties.staticBaseUrl();
        if (!StringUtils.hasText(baseUrl) || "/".equals(baseUrl.trim())) {
            return "/" + relativePath;
        }
        String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        return normalizedBaseUrl + "/" + relativePath;
    }

    private String resolveFileExtension(String contentType) {
        return switch (contentType.toLowerCase(Locale.ROOT)) {
            case "image/png" -> "png";
            case "image/webp" -> "webp";
            case "image/jpeg", "image/jpg" -> "jpg";
            default -> throw new ApiException(ErrorCode.UNSUPPORTED_IMAGE_TYPE);
        };
    }

    private String normalizeRelativePath(String value) {
        String normalizedValue = value == null ? "" : value.replace('\\', '/');
        while (normalizedValue.startsWith("/")) {
            normalizedValue = normalizedValue.substring(1);
        }
        return normalizedValue;
    }

    private String normalizeOptionalText(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }

    private String normalizeRequiredText(String value) {
        String normalized = normalizeOptionalText(value);
        if (normalized == null) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "message_text는 필수입니다.");
        }
        return normalized;
    }
}
