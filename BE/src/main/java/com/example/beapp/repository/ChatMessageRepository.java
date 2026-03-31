package com.example.beapp.repository;

import java.util.List;
import java.util.Optional;

import com.example.beapp.model.ChatMessage;

public interface ChatMessageRepository {
    ChatMessage save(ChatMessage chatMessage);

    List<ChatMessage> findAllByRoomId(Long roomId);

    List<ChatMessage> findAllByRoomIdAfterId(Long roomId, Long afterId);

    Optional<ChatMessage> findLatestByRoomId(Long roomId);

    void deleteByRoomId(Long roomId);
}
