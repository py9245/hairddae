package com.example.beapp.repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.ChatMessage;

@Repository
@Profile("test")
public class InMemoryChatMessageRepository implements ChatMessageRepository {

    private final AtomicLong sequence = new AtomicLong(1);
    private final Map<Long, ChatMessage> messages = new ConcurrentHashMap<>();

    @Override
    public ChatMessage save(ChatMessage chatMessage) {
        OffsetDateTime now = OffsetDateTime.now();
        ChatMessage saved = new ChatMessage(
                sequence.getAndIncrement(),
                chatMessage.roomId(),
                chatMessage.senderUserId(),
                chatMessage.messageType(),
                chatMessage.messageText(),
                chatMessage.imageUrl(),
                now,
                chatMessage.readAt());
        messages.put(saved.id(), saved);
        return saved;
    }

    @Override
    public List<ChatMessage> findAllByRoomId(Long roomId) {
        return messages.values().stream()
                .filter(message -> message.roomId().equals(roomId))
                .sorted(java.util.Comparator.comparing(ChatMessage::id))
                .toList();
    }

    @Override
    public List<ChatMessage> findAllByRoomIdAfterId(Long roomId, Long afterId) {
        return messages.values().stream()
                .filter(message -> message.roomId().equals(roomId) && message.id() > afterId)
                .sorted(java.util.Comparator.comparing(ChatMessage::id))
                .toList();
    }

    @Override
    public Optional<ChatMessage> findLatestByRoomId(Long roomId) {
        return messages.values().stream()
                .filter(message -> message.roomId().equals(roomId))
                .max(java.util.Comparator.comparing(ChatMessage::id));
    }

    @Override
    public void deleteByRoomId(Long roomId) {
        messages.entrySet().removeIf(entry -> entry.getValue().roomId().equals(roomId));
    }
}
