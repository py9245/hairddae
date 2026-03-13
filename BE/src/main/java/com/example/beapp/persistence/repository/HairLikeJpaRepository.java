package com.example.beapp.persistence.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import com.example.beapp.persistence.entity.HairLikeEntity;

public interface HairLikeJpaRepository extends JpaRepository<HairLikeEntity, Long> {
    boolean existsByUser_UserIdAndHair_Id(String userId, Long hairId);

    Optional<HairLikeEntity> findByUser_UserIdAndHair_Id(String userId, Long hairId);

    @Query("""
            select hl
            from HairLikeEntity hl
            join fetch hl.hair
            where hl.user.userId = :userId
            order by hl.createdAt desc
            """)
    List<HairLikeEntity> findAllByUserIdWithHairOrderByCreatedAtDesc(@Param("userId") String userId);

    @Query("""
            select hl.hair.id
            from HairLikeEntity hl
            where hl.user.userId = :userId
            and hl.hair.id in :hairIds
            """)
    List<Long> findLikedHairIds(@Param("userId") String userId, @Param("hairIds") List<Long> hairIds);
}
