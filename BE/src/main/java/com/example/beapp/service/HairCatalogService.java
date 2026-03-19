package com.example.beapp.service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.context.annotation.Profile;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.HairItem;
import com.example.beapp.api.dto.hairs.HairCard;
import com.example.beapp.api.dto.hairs.HairDetailResponse;
import com.example.beapp.api.dto.hairs.HairLikeResponse;
import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.api.dto.hairs.HairRecommendResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.entity.HairLikeEntity;
import com.example.beapp.persistence.entity.HistoryEntity;
import com.example.beapp.persistence.entity.UserEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.example.beapp.persistence.repository.HairLikeJpaRepository;
import com.example.beapp.persistence.repository.HistoryJpaRepository;
import com.example.beapp.persistence.repository.UserJpaRepository;

@Service
@Profile("!test")
public class HairCatalogService {

    private final HairJpaRepository hairJpaRepository;
    private final HairLikeJpaRepository hairLikeJpaRepository;
    private final HistoryJpaRepository historyJpaRepository;
    private final UserJpaRepository userJpaRepository;
    private final HairAssetRecommendationService hairAssetRecommendationService;

    public HairCatalogService(
            HairJpaRepository hairJpaRepository,
            HairLikeJpaRepository hairLikeJpaRepository,
            HistoryJpaRepository historyJpaRepository,
            UserJpaRepository userJpaRepository,
            HairAssetRecommendationService hairAssetRecommendationService
    ) {
        this.hairJpaRepository = hairJpaRepository;
        this.hairLikeJpaRepository = hairLikeJpaRepository;
        this.historyJpaRepository = historyJpaRepository;
        this.userJpaRepository = userJpaRepository;
        this.hairAssetRecommendationService = hairAssetRecommendationService;
    }

    @Transactional(readOnly = true)
    public List<HairItem> getCustomRankItems(String userId, int size) {
        Page<HairEntity> page = hairJpaRepository.findByActiveTrue(PageRequest.of(
                0,
                Math.max(1, size),
                Sort.by(Sort.Order.desc("likeCount"), Sort.Order.desc("viewCount"), Sort.Order.asc("id"))));
        return toHairItems(page.getContent());
    }

    @Transactional(readOnly = true)
    public List<HairItem> getNormalRankItems(String category, String sort, int size) {
        Pageable pageable = PageRequest.of(0, Math.max(1, size), resolveListSort(sort));
        Page<HairEntity> page = StringUtils.hasText(category)
                ? hairJpaRepository.findByActiveTrueAndCategoryIgnoreCase(category, pageable)
                : hairJpaRepository.findByActiveTrue(pageable);
        return toHairItems(page.getContent());
    }

    @Transactional(readOnly = true)
    public HairListResponse getHairList(String userId, int page, int size, String category, String sort) {
        Pageable pageable = PageRequest.of(Math.max(0, page), Math.max(1, size), resolveListSort(sort));
        Page<HairEntity> result = StringUtils.hasText(category)
                ? hairJpaRepository.findByActiveTrueAndCategoryIgnoreCase(category, pageable)
                : hairJpaRepository.findByActiveTrue(pageable);
        Set<Long> likedHairIds = resolveLikedHairIds(userId, result.getContent());
        List<HairCard> hairList = result.getContent().stream()
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId()), latestViewedAt(hair)))
                .toList();
        return HairListResponse.ok(result.getTotalElements(), hairList);
    }

    @Transactional(readOnly = true)
    public HairDetailResponse getHairDetail(String userId, Long hairId) {
        HairEntity hair = getRequiredHair(hairId);
        boolean liked = StringUtils.hasText(userId) && hairLikeJpaRepository.existsByUser_UserIdAndHair_Id(userId, hairId);
        return HairDetailResponse.ok(
                hair.getId().intValue(),
                hair.getName(),
                hair.getSlug(),
                hair.getCategory(),
                hair.getPreviewImageUrl(),
                safeCount(hair.getLikeCount()),
                safeCount(hair.getViewCount()),
                latestViewedAt(hair),
                liked,
                hair.getDescription(),
                hair.getDatasetCode(),
                hair.getDatasetRootUrl(),
                hair.getAssetIndexUrl(),
                hair.getRepresentativeAssetId());
    }

    @Transactional(readOnly = true)
    public HairRecommendResponse recommend(Long hairId, Integer yaw1deg, Integer pitch1deg, Integer roll1deg) {
        HairEntity hair = hairId == null
                ? hairJpaRepository.findByActiveTrue(PageRequest.of(0, 1, Sort.by(Sort.Order.asc("id"))))
                        .stream()
                        .findFirst()
                        .orElseThrow(() -> new ApiException(ErrorCode.HAIR_NOT_FOUND))
                : getRequiredHair(hairId);
        return HairRecommendResponse.ok(
                hair.getId().intValue(),
                hair.getName(),
                hair.getDatasetCode(),
                hair.getDatasetRootUrl(),
                hair.getAssetIndexUrl(),
                hairAssetRecommendationService.recommend(hair, yaw1deg, pitch1deg, roll1deg));
    }

    @Transactional
    public HairLikeResponse like(String userId, Long hairId) {
        UserEntity user = getRequiredUser(userId);
        HairEntity hair = getRequiredHair(hairId);

        if (hairLikeJpaRepository.existsByUser_UserIdAndHair_Id(userId, hairId)) {
            return HairLikeResponse.of(hairId.intValue(), true, safeCount(hair.getLikeCount()), "좋아요 유지");
        }

        hairLikeJpaRepository.save(new HairLikeEntity(user, hair));
        hair.incrementLikeCount();
        hairJpaRepository.save(hair);
        return HairLikeResponse.of(hairId.intValue(), true, safeCount(hair.getLikeCount()), "좋아요 등록 완료");
    }

    @Transactional
    public HairLikeResponse unlike(String userId, Long hairId) {
        HairEntity hair = getRequiredHair(hairId);
        hairLikeJpaRepository.findByUser_UserIdAndHair_Id(userId, hairId)
                .ifPresent(hairLike -> {
                    hairLikeJpaRepository.delete(hairLike);
                    hair.decrementLikeCount();
                });
        hairJpaRepository.save(hair);
        return HairLikeResponse.of(hairId.intValue(), false, safeCount(hair.getLikeCount()), "좋아요 취소 완료");
    }

    @Transactional
    public void recordHistory(String userId, Integer hairId, Integer viewSec) {
        UserEntity user = getRequiredUser(userId);
        HairEntity hair = getRequiredHair(hairId.longValue());
        historyJpaRepository.save(new HistoryEntity(user, hair, viewSec == null ? 5 : viewSec));
        hair.incrementViewCount();
        hairJpaRepository.save(hair);
    }

    @Transactional(readOnly = true)
    public List<HairItem> getBookmarkItems(String userId, int page, int size, boolean onlyActive) {
        List<HairLikeEntity> likes = hairLikeJpaRepository.findAllByUserIdWithHairOrderByCreatedAtDesc(userId);
        List<HairItem> items = likes.stream()
                .filter(hairLike -> !onlyActive || Boolean.TRUE.equals(hairLike.getHair().getActive()))
                .map(hairLike -> new HairItem(
                        hairLike.getHair().getId().intValue(),
                        hairLike.getHair().getCategory(),
                        hairLike.getHair().getPreviewImageUrl(),
                        safeCount(hairLike.getHair().getLikeCount()),
                        safeCount(hairLike.getHair().getViewCount()),
                        hairLike.getCreatedAt()))
                .toList();
        return paginate(items, page, size);
    }

    @Transactional(readOnly = true)
    public List<HairItem> getRecentItems(String userId, int minViewSec, int page, int size) {
        List<HistoryEntity> histories = historyJpaRepository.findRecentByUserIdWithHair(userId, minViewSec);
        LinkedHashMap<Long, HistoryEntity> deduplicated = new LinkedHashMap<>();
        for (HistoryEntity history : histories) {
            deduplicated.putIfAbsent(history.getHair().getId(), history);
        }

        List<HairItem> items = deduplicated.values().stream()
                .map(history -> new HairItem(
                        history.getHair().getId().intValue(),
                        history.getHair().getCategory(),
                        history.getHair().getPreviewImageUrl(),
                        safeCount(history.getHair().getLikeCount()),
                        safeCount(history.getHair().getViewCount()),
                        history.getViewedAt()))
                .toList();
        return paginate(items, page, size);
    }

    private List<HairItem> toHairItems(List<HairEntity> hairs) {
        return hairs.stream()
                .map(hair -> new HairItem(
                        hair.getId().intValue(),
                        hair.getCategory(),
                        hair.getPreviewImageUrl(),
                        safeCount(hair.getLikeCount()),
                        safeCount(hair.getViewCount()),
                        latestViewedAt(hair)))
                .toList();
    }

    private HairCard toHairCard(HairEntity hair, boolean liked, OffsetDateTime latestViewedAt) {
        return new HairCard(
                hair.getId().intValue(),
                hair.getName(),
                hair.getSlug(),
                hair.getCategory(),
                hair.getPreviewImageUrl(),
                safeCount(hair.getLikeCount()),
                safeCount(hair.getViewCount()),
                latestViewedAt,
                liked,
                hair.getDatasetCode());
    }

    private Set<Long> resolveLikedHairIds(String userId, List<HairEntity> hairs) {
        if (!StringUtils.hasText(userId) || hairs.isEmpty()) {
            return Set.of();
        }
        List<Long> hairIds = hairs.stream().map(HairEntity::getId).toList();
        return hairLikeJpaRepository.findLikedHairIds(userId, hairIds).stream().collect(Collectors.toSet());
    }

    private OffsetDateTime latestViewedAt(HairEntity hair) {
        return historyJpaRepository.findLatestViewedAtByHairId(hair.getId());
    }

    private HairEntity getRequiredHair(Long hairId) {
        return hairJpaRepository.findByIdAndActiveTrue(hairId)
                .orElseThrow(() -> new ApiException(ErrorCode.HAIR_NOT_FOUND));
    }

    private UserEntity getRequiredUser(String userId) {
        return userJpaRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private Sort resolveListSort(String sort) {
        if (!StringUtils.hasText(sort)) {
            return Sort.by(Sort.Order.asc("id"));
        }
        return switch (sort.trim().toLowerCase()) {
            case "popular", "like" -> Sort.by(Sort.Order.desc("likeCount"), Sort.Order.desc("viewCount"), Sort.Order.asc("id"));
            case "view", "download" -> Sort.by(Sort.Order.desc("viewCount"), Sort.Order.desc("likeCount"), Sort.Order.asc("id"));
            case "recent" -> Sort.by(Sort.Order.desc("updatedAt"), Sort.Order.asc("id"));
            default -> Sort.by(Sort.Order.asc("id"));
        };
    }

    private int safeCount(Integer value) {
        return value == null ? 0 : value;
    }

    private <T> List<T> paginate(List<T> values, int page, int size) {
        int safePage = Math.max(0, page);
        int safeSize = Math.max(1, size);
        int fromIndex = Math.min(safePage * safeSize, values.size());
        int toIndex = Math.min(fromIndex + safeSize, values.size());
        return new ArrayList<>(values.subList(fromIndex, toIndex));
    }
}
