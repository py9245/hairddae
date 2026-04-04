package com.example.beapp.repository;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

import com.example.beapp.model.ChatRoom;

@Repository
@Profile("test")
public class InMemoryChatRoomRepository implements ChatRoomRepository {

    private final AtomicLong sequence = new AtomicLong(1);
    private final Map<Long, ChatRoom> rooms = new ConcurrentHashMap<>();

    @Override
    public Optional<ChatRoom> findByParticipants(String customerUserId, String designerUserId) {
        return rooms.values().stream()
                .filter(room -> room.customerUserId().equals(customerUserId) && room.designerUserId().equals(designerUserId))
                .findFirst();
    }

    @Override
    public Optional<ChatRoom> findById(Long roomId) {
        return Optional.ofNullable(rooms.get(roomId));
    }

    @Override
    public List<ChatRoom> findAllByParticipant(String userId) {
        return rooms.values().stream()
                .filter(room -> room.customerUserId().equals(userId) || room.designerUserId().equals(userId))
                .sorted(Comparator.comparing(ChatRoom::id))
                .toList();
    }

    @Override
    public ChatRoom save(ChatRoom chatRoom) {
        OffsetDateTime now = OffsetDateTime.now();
        ChatRoom saved;
        if (chatRoom.id() == null) {
            saved = new ChatRoom(
                    sequence.getAndIncrement(),
                    chatRoom.customerUserId(),
                    chatRoom.designerUserId(),
                    chatRoom.sourceHairId(),
                    now,
                    now);
        } else {
            ChatRoom existing = rooms.get(chatRoom.id());
            saved = new ChatRoom(
                    chatRoom.id(),
                    chatRoom.customerUserId(),
                    chatRoom.designerUserId(),
                    chatRoom.sourceHairId(),
                    existing != null ? existing.createdAt() : now,
                    now);
        }
        rooms.put(saved.id(), saved);
        return saved;
    }

    @Override
    public void deleteAllByUserId(String userId) {
        List<Long> targetIds = new ArrayList<>();
        for (ChatRoom room : rooms.values()) {
            if (room.customerUserId().equals(userId) || room.designerUserId().equals(userId)) {
                targetIds.add(room.id());
            }
        }
        targetIds.forEach(rooms::remove);
    }
}
