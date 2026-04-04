package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;

import com.example.beapp.persistence.entity.ChatMessageEntity;

public interface ChatMessageJpaRepository extends JpaRepository<ChatMessageEntity, Long> {
    List<ChatMessageEntity> findAllByRoomIdOrderByIdAsc(Long roomId);

    List<ChatMessageEntity> findAllByRoomIdAndIdGreaterThanOrderByIdAsc(Long roomId, Long afterId);

    Optional<ChatMessageEntity> findTopByRoomIdOrderByIdDesc(Long roomId);

    void deleteByRoomId(Long roomId);
}
