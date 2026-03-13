package com.example.beapp.persistence.repository;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.example.beapp.persistence.entity.HistoryEntity;

public interface HistoryJpaRepository extends JpaRepository<HistoryEntity, Long> {
    @Query("""
            select h
            from HistoryEntity h
            join fetch h.hair
            where h.user.userId = :userId
            and h.viewSeconds >= :minViewSec
            order by h.viewedAt desc
            """)
    List<HistoryEntity> findRecentByUserIdWithHair(
            @Param("userId") String userId,
            @Param("minViewSec") Integer minViewSec);

    Optional<HistoryEntity> findTopByHair_IdOrderByViewedAtDesc(Long hairId);

    @Query("""
            select max(h.viewedAt)
            from HistoryEntity h
            where h.hair.id = :hairId
            """)
    OffsetDateTime findLatestViewedAtByHairId(@Param("hairId") Long hairId);
}
