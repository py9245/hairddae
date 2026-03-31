package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import com.example.beapp.model.ChatMessage;
import com.example.beapp.persistence.entity.ChatMessageEntity;
import com.example.beapp.repository.ChatMessageRepository;

@Repository
@Primary
@Profile("!test")
public class JpaChatMessageRepositoryAdapter implements ChatMessageRepository {

    private final ChatMessageJpaRepository chatMessageJpaRepository;

    public JpaChatMessageRepositoryAdapter(ChatMessageJpaRepository chatMessageJpaRepository) {
        this.chatMessageJpaRepository = chatMessageJpaRepository;
    }

    @Override
    @Transactional
    public ChatMessage save(ChatMessage chatMessage) {
        ChatMessageEntity saved = chatMessageJpaRepository.save(new ChatMessageEntity(
                chatMessage.roomId(),
                chatMessage.senderUserId(),
                chatMessage.messageType(),
                chatMessage.messageText(),
                chatMessage.imageUrl()));
        return toModel(saved);
    }

    @Override
    public List<ChatMessage> findAllByRoomId(Long roomId) {
        return chatMessageJpaRepository.findAllByRoomIdOrderByIdAsc(roomId).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    public List<ChatMessage> findAllByRoomIdAfterId(Long roomId, Long afterId) {
        return chatMessageJpaRepository.findAllByRoomIdAndIdGreaterThanOrderByIdAsc(roomId, afterId).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    public Optional<ChatMessage> findLatestByRoomId(Long roomId) {
        return chatMessageJpaRepository.findTopByRoomIdOrderByIdDesc(roomId).map(this::toModel);
    }

    @Override
    @Transactional
    public void deleteByRoomId(Long roomId) {
        chatMessageJpaRepository.deleteByRoomId(roomId);
    }

    private ChatMessage toModel(ChatMessageEntity entity) {
        return new ChatMessage(
                entity.getId(),
                entity.getRoomId(),
                entity.getSenderUserId(),
                entity.getMessageType(),
                entity.getMessageText(),
                entity.getImageUrl(),
                entity.getCreatedAt(),
                entity.getReadAt());
    }
}
