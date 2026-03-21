package com.example.beapp.service;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
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

import com.example.beapp.api.dto.hairs.HairCard;
import com.example.beapp.api.dto.hairs.HairDetailResponse;
import com.example.beapp.api.dto.hairs.HairLikeResponse;
import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.api.dto.hairs.HairRecommendResponse;
import com.example.beapp.api.dto.home.CategoryListResponse;
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
    public List<HairCard> getCustomRankCards(String userId, int size) {
        List<HairEntity> candidates = hairJpaRepository.findByActiveTrue(PageRequest.of(
                0,
                Math.max(20, Math.max(1, size) * 4),
                popularSort())).getContent();
        Set<Long> likedHairIds = resolveLikedHairIds(userId, candidates);
        Map<String, Integer> preferenceWeights = resolveCategoryPreferenceWeights(userId);

        return candidates.stream()
                .sorted(Comparator
                        .comparingInt((HairEntity hair) -> preferenceWeights.getOrDefault(normalizeCategoryKey(hair.getCategory()), 0))
                        .reversed()
                        .thenComparing(HairEntity::getLikeCount, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(HairEntity::getViewCount, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(HairEntity::getCreatedAt, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(HairEntity::getId))
                .limit(Math.max(1, size))
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<HairCard> getBestRankCards(String userId, int size) {
        List<HairEntity> hairs = hairJpaRepository.findByActiveTrue(PageRequest.of(0, Math.max(1, size), popularSort())).getContent();
        Set<Long> likedHairIds = resolveLikedHairIds(userId, hairs);
        return hairs.stream()
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<HairCard> getLatestRankCards(String userId, int size) {
        List<HairEntity> hairs = hairJpaRepository.findByActiveTrue(PageRequest.of(0, Math.max(1, size), latestSort())).getContent();
        Set<Long> likedHairIds = resolveLikedHairIds(userId, hairs);
        return hairs.stream()
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public List<CategoryListResponse.CategoryItem> getCategoryItems() {
        List<HairEntity> hairs = hairJpaRepository.findByActiveTrue(PageRequest.of(0, 500, popularSort())).getContent();
        LinkedHashMap<String, CategoryListResponse.CategoryItem> items = new LinkedHashMap<>();
        String allPreviewImage = hairs.isEmpty() ? null : hairs.get(0).getPreviewImageUrl();
        items.put("all", new CategoryListResponse.CategoryItem("all", "전체", allPreviewImage));

        for (HairEntity hair : hairs) {
            if (!StringUtils.hasText(hair.getCategory())) {
                continue;
            }
            items.putIfAbsent(
                    hair.getCategory(),
                    new CategoryListResponse.CategoryItem(
                            hair.getCategory(),
                            hair.getCategory(),
                            hair.getPreviewImageUrl()));
        }
        return new ArrayList<>(items.values());
    }

    @Transactional(readOnly = true)
    public List<HairCard> getCategoryCards(String userId, String categoryId, int size) {
        Pageable pageable = PageRequest.of(0, Math.max(1, size), latestSort());
        Page<HairEntity> page = isAllCategory(categoryId)
                ? hairJpaRepository.findByActiveTrue(pageable)
                : hairJpaRepository.findByActiveTrueAndCategoryIgnoreCase(categoryId, pageable);
        Set<Long> likedHairIds = resolveLikedHairIds(userId, page.getContent());
        return page.getContent().stream()
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId())))
                .toList();
    }

    @Transactional(readOnly = true)
    public HairListResponse getHairList(String userId, int page, int size, String category, String sort) {
        Pageable pageable = PageRequest.of(Math.max(0, page), Math.max(1, size), resolveListSort(sort));
        Page<HairEntity> result = StringUtils.hasText(category)
                ? hairJpaRepository.findByActiveTrueAndCategoryIgnoreCase(category, pageable)
                : hairJpaRepository.findByActiveTrue(pageable);
        Set<Long> likedHairIds = resolveLikedHairIds(userId, result.getContent());
        List<HairCard> hairList = result.getContent().stream()
                .map(hair -> toHairCard(hair, likedHairIds.contains(hair.getId())))
                .toList();
        return HairListResponse.ok(result.getTotalElements(), hairList);
    }

    @Transactional(readOnly = true)
    public HairListResponse getCameraList(String userId, int page, int size) {
        List<HairCard> items = buildRecentAppliedCards(userId, 0);
        return HairListResponse.ok(items.size(), paginate(items, page, size));
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
    public List<HairCard> getLikeCards(String userId, int page, int size, boolean onlyActive) {
        List<HairLikeEntity> likes = hairLikeJpaRepository.findAllByUserIdWithHairOrderByCreatedAtDesc(userId);
        List<HairCard> items = likes.stream()
                .filter(hairLike -> !onlyActive || Boolean.TRUE.equals(hairLike.getHair().getActive()))
                .map(hairLike -> toHairCard(hairLike.getHair(), true))
                .toList();
        return paginate(items, page, size);
    }

    @Transactional(readOnly = true)
    public List<HairCard> getRecentAppliedCards(String userId, int minViewSec, int page, int size) {
        return paginate(buildRecentAppliedCards(userId, minViewSec), page, size);
    }

    private HairCard toHairCard(HairEntity hair, boolean liked) {
        return new HairCard(
                hair.getId().intValue(),
                hair.getPreviewImageUrl(),
                liked,
                buildHookText(hair),
                hair.getName(),
                hair.getCategory(),
                hair.getCreatedAt());
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

    private Map<String, Integer> resolveCategoryPreferenceWeights(String userId) {
        Map<String, Integer> preferenceWeights = new HashMap<>();
        if (!StringUtils.hasText(userId)) {
            return preferenceWeights;
        }

        List<HairLikeEntity> likes = hairLikeJpaRepository.findAllByUserIdWithHairOrderByCreatedAtDesc(userId);
        for (HairLikeEntity like : likes) {
            incrementWeight(preferenceWeights, like.getHair().getCategory(), 3);
        }

        List<HistoryEntity> histories = historyJpaRepository.findRecentByUserIdWithHair(userId, 0);
        int weight = 5;
        for (HistoryEntity history : histories) {
            incrementWeight(preferenceWeights, history.getHair().getCategory(), weight);
            if (weight > 1) {
                weight -= 1;
            }
        }
        return preferenceWeights;
    }

    private void incrementWeight(Map<String, Integer> preferenceWeights, String category, int weight) {
        if (!StringUtils.hasText(category)) {
            return;
        }
        preferenceWeights.merge(normalizeCategoryKey(category), weight, Integer::sum);
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
            return latestSort();
        }
        return switch (sort.trim().toLowerCase()) {
            case "popular", "like", "best" -> popularSort();
            case "latest", "recent" -> latestSort();
            case "view", "download" -> Sort.by(Sort.Order.desc("viewCount"), Sort.Order.desc("likeCount"), Sort.Order.desc("createdAt"));
            default -> latestSort();
        };
    }

    private Sort popularSort() {
        return Sort.by(
                Sort.Order.desc("likeCount"),
                Sort.Order.desc("viewCount"),
                Sort.Order.desc("createdAt"),
                Sort.Order.asc("id"));
    }

    private Sort latestSort() {
        return Sort.by(
                Sort.Order.desc("createdAt"),
                Sort.Order.asc("id"));
    }

    private String buildHookText(HairEntity hair) {
        if (StringUtils.hasText(hair.getDescription())) {
            return hair.getDescription();
        }
        return "%s 스타일을 만나보세요.".formatted(hair.getName());
    }

    private boolean isAllCategory(String categoryId) {
        return !StringUtils.hasText(categoryId)
                || "all".equalsIgnoreCase(categoryId.trim())
                || "전체".equals(categoryId.trim());
    }

    private String normalizeCategoryKey(String category) {
        return category == null ? "" : category.trim().toLowerCase();
    }

    private int safeCount(Integer value) {
        return value == null ? 0 : value;
    }

    private List<HairCard> buildRecentAppliedCards(String userId, int minViewSec) {
        List<HistoryEntity> histories = historyJpaRepository.findRecentByUserIdWithHair(userId, minViewSec);
        LinkedHashMap<Long, HistoryEntity> deduplicated = new LinkedHashMap<>();
        for (HistoryEntity history : histories) {
            deduplicated.putIfAbsent(history.getHair().getId(), history);
        }

        List<HairEntity> hairs = deduplicated.values().stream()
                .map(HistoryEntity::getHair)
                .toList();
        Set<Long> likedHairIds = resolveLikedHairIds(userId, hairs);

        return deduplicated.values().stream()
                .map(history -> toHairCard(history.getHair(), likedHairIds.contains(history.getHair().getId())))
                .toList();
    }

    private <T> List<T> paginate(List<T> values, int page, int size) {
        int safePage = Math.max(0, page);
        int safeSize = Math.max(1, size);
        int fromIndex = Math.min(safePage * safeSize, values.size());
        int toIndex = Math.min(fromIndex + safeSize, values.size());
        return new ArrayList<>(values.subList(fromIndex, toIndex));
    }
}
