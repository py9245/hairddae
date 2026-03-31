package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.example.beapp.persistence.entity.ChatRoomEntity;

public interface ChatRoomJpaRepository extends JpaRepository<ChatRoomEntity, Long> {
    Optional<ChatRoomEntity> findByCustomerUserIdAndDesignerUserId(String customerUserId, String designerUserId);

    @Query("""
            select cr
            from ChatRoomEntity cr
            where cr.customerUserId = :userId
               or cr.designerUserId = :userId
            order by cr.createdAt desc, cr.id desc
            """)
    List<ChatRoomEntity> findAllByParticipant(@Param("userId") String userId);

    void deleteByCustomerUserIdOrDesignerUserId(String customerUserId, String designerUserId);
}
