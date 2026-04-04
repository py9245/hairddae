package com.example.beapp.repository;

import java.util.List;
import java.util.Optional;

import com.example.beapp.model.ChatRoom;

public interface ChatRoomRepository {
    Optional<ChatRoom> findByParticipants(String customerUserId, String designerUserId);

    Optional<ChatRoom> findById(Long roomId);

    List<ChatRoom> findAllByParticipant(String userId);

    ChatRoom save(ChatRoom chatRoom);

    void deleteAllByUserId(String userId);
}
