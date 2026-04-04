package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

import com.example.beapp.model.ChatRoom;
import com.example.beapp.persistence.entity.ChatRoomEntity;
import com.example.beapp.repository.ChatRoomRepository;

@Repository
@Primary
@Profile("!test")
public class JpaChatRoomRepositoryAdapter implements ChatRoomRepository {

    private final ChatRoomJpaRepository chatRoomJpaRepository;

    public JpaChatRoomRepositoryAdapter(ChatRoomJpaRepository chatRoomJpaRepository) {
        this.chatRoomJpaRepository = chatRoomJpaRepository;
    }

    @Override
    public Optional<ChatRoom> findByParticipants(String customerUserId, String designerUserId) {
        return chatRoomJpaRepository.findByCustomerUserIdAndDesignerUserId(customerUserId, designerUserId)
                .map(this::toModel);
    }

    @Override
    public Optional<ChatRoom> findById(Long roomId) {
        return chatRoomJpaRepository.findById(roomId).map(this::toModel);
    }

    @Override
    public List<ChatRoom> findAllByParticipant(String userId) {
        return chatRoomJpaRepository.findAllByParticipant(userId).stream()
                .map(this::toModel)
                .toList();
    }

    @Override
    @Transactional
    public ChatRoom save(ChatRoom chatRoom) {
        ChatRoomEntity entity = chatRoom.id() == null
                ? new ChatRoomEntity(chatRoom.customerUserId(), chatRoom.designerUserId(), chatRoom.sourceHairId())
                : chatRoomJpaRepository.findById(chatRoom.id())
                        .map(existing -> existing.update(
                                chatRoom.customerUserId(),
                                chatRoom.designerUserId(),
                                chatRoom.sourceHairId()))
                        .orElseGet(() -> new ChatRoomEntity(
                                chatRoom.customerUserId(),
                                chatRoom.designerUserId(),
                                chatRoom.sourceHairId()));
        return toModel(chatRoomJpaRepository.save(entity));
    }

    @Override
    @Transactional
    public void deleteAllByUserId(String userId) {
        chatRoomJpaRepository.deleteByCustomerUserIdOrDesignerUserId(userId, userId);
    }

    private ChatRoom toModel(ChatRoomEntity entity) {
        return new ChatRoom(
                entity.getId(),
                entity.getCustomerUserId(),
                entity.getDesignerUserId(),
                entity.getSourceHairId(),
                entity.getCreatedAt(),
                entity.getUpdatedAt());
    }
}
