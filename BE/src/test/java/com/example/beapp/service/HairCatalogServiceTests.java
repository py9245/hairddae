package com.example.beapp.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertIterableEquals;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Sort;
import org.springframework.test.util.ReflectionTestUtils;

import com.example.beapp.api.dto.home.CategoryListResponse;
import com.example.beapp.persistence.entity.HairCategoryEntity;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairCategoryJpaRepository;
import com.example.beapp.persistence.repository.HairJpaRepository;
import com.example.beapp.persistence.repository.HairLikeJpaRepository;
import com.example.beapp.persistence.repository.HistoryJpaRepository;
import com.example.beapp.persistence.repository.UserJpaRepository;

@ExtendWith(MockitoExtension.class)
class HairCatalogServiceTests {

    @Mock
    private HairJpaRepository hairJpaRepository;

    @Mock
    private HairCategoryJpaRepository hairCategoryJpaRepository;

    @Mock
    private HairLikeJpaRepository hairLikeJpaRepository;

    @Mock
    private HistoryJpaRepository historyJpaRepository;

    @Mock
    private UserJpaRepository userJpaRepository;

    @Mock
    private HairStaticUrlResolver hairStaticUrlResolver;

    @InjectMocks
    private HairCatalogService hairCatalogService;

    @Test
    void getCategoryItemsReturnsConfiguredCategoriesWithActiveHairOnly() {
        HairEntity dandyHair = new HairEntity("댄디 1", "댄디컷", "/static/hair/dandy.png", "desc");
        HairEntity partHair = new HairEntity("가르마 1", "가르마", "/static/hair/part.png", "desc");

        HairCategoryEntity partCategory = new HairCategoryEntity("가르마", "가르마", "/static/category/part.png", null);
        HairCategoryEntity dandyCategory = new HairCategoryEntity("댄디컷", "댄디컷", null, null);
        HairCategoryEntity emptyCategory = new HairCategoryEntity("히피펌", "히피펌", "/static/category/hippie.png", null);

        given(hairJpaRepository.findByActiveTrue(org.mockito.ArgumentMatchers.any(Sort.class)))
                .willReturn(List.of(dandyHair, partHair));
        given(hairCategoryJpaRepository.findAllByActiveTrueOrderByDisplayOrderAscCreatedAtAsc())
                .willReturn(List.of(partCategory, dandyCategory, emptyCategory));
        given(hairStaticUrlResolver.resolvePreviewImageUrl(dandyHair)).willReturn("/static/hair/dandy.png");

        List<CategoryListResponse.CategoryItem> items = hairCatalogService.getCategoryItems();

        assertEquals(3, items.size());
        assertIterableEquals(
                List.of("all", "가르마", "댄디컷"),
                items.stream().map(CategoryListResponse.CategoryItem::categoryID).toList());
        assertEquals("/static/hair/dandy.png", items.get(0).image());
        assertEquals("/static/category/part.png", items.get(1).image());
        assertEquals("/static/hair/dandy.png", items.get(2).image());
    }

    @Test
    void getCategoryCardsUsesCategoryIdFilter() {
        HairEntity hair = new HairEntity("가르마 1", "가르마", "/static/hair/part.png", "desc");
        ReflectionTestUtils.setField(hair, "id", 1L);
        given(hairJpaRepository.findByActiveTrueAndCategoryIdIgnoreCase(anyString(), org.mockito.ArgumentMatchers.any(Sort.class)))
                .willReturn(List.of(hair));
        given(hairLikeJpaRepository.findLikedHairIds(anyString(), anyList())).willReturn(List.of());
        given(hairStaticUrlResolver.resolvePreviewImageUrl(hair)).willReturn("/static/hair/part.png");

        var result = hairCatalogService.getCategoryCards("TestUser01", "가르마");

        assertEquals(1, result.size());
        assertEquals("가르마", result.get(0).category());
        then(hairJpaRepository).should().findByActiveTrueAndCategoryIdIgnoreCase(anyString(), org.mockito.ArgumentMatchers.any(Sort.class));
    }
}
