package com.example.beapp.service;

import java.util.LinkedHashSet;
import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.example.beapp.api.dto.mypage.DesignerSpecialtiesRequest;
import com.example.beapp.api.dto.mypage.DesignerSpecialtiesResponse;
import com.example.beapp.api.dto.mypage.DesignerSpecialtiesUpsertResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerSpecialtyRepository;
import com.example.beapp.repository.HairCategoryLookupRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class DesignerSpecialtyService {

    private final UserAccountRepository userAccountRepository;
    private final DesignerSpecialtyRepository designerSpecialtyRepository;
    private final HairCategoryLookupRepository hairCategoryLookupRepository;

    public DesignerSpecialtyService(
            UserAccountRepository userAccountRepository,
            DesignerSpecialtyRepository designerSpecialtyRepository,
            HairCategoryLookupRepository hairCategoryLookupRepository) {
        this.userAccountRepository = userAccountRepository;
        this.designerSpecialtyRepository = designerSpecialtyRepository;
        this.hairCategoryLookupRepository = hairCategoryLookupRepository;
    }

    @Transactional
    public DesignerSpecialtiesUpsertResponse replace(String userId, DesignerSpecialtiesRequest request) {
        UserAccount userAccount = getRequiredUser(userId);
        verifyApprovedDesigner(userAccount);

        List<String> normalizedCategoryIds = normalizeCategoryIds(request.categoryIds());
        validateCategoryIds(normalizedCategoryIds);

        designerSpecialtyRepository.replaceAll(userId, normalizedCategoryIds);

        return DesignerSpecialtiesUpsertResponse.ok();
    }

    @Transactional(readOnly = true)
    public DesignerSpecialtiesResponse get(String userId) {
        UserAccount userAccount = getRequiredUser(userId);
        verifyApprovedDesigner(userAccount);

        List<DesignerSpecialtiesResponse.DesignerSpecialtyItem> items = designerSpecialtyRepository.findAllByUserId(userId).stream()
                .map(specialty -> hairCategoryLookupRepository.findByCategoryId(specialty.categoryId())
                        .map(this::toItem)
                        .orElseGet(() -> new DesignerSpecialtiesResponse.DesignerSpecialtyItem(
                                specialty.categoryId(),
                                specialty.categoryId())))
                .toList();

        return DesignerSpecialtiesResponse.ok(items);
    }

    private List<String> normalizeCategoryIds(List<String> rawCategoryIds) {
        return rawCategoryIds.stream()
                .map(String::trim)
                .filter(value -> !value.isEmpty())
                .collect(java.util.stream.Collectors.collectingAndThen(
                        java.util.stream.Collectors.toCollection(LinkedHashSet::new),
                        List::copyOf));
    }

    private void validateCategoryIds(List<String> categoryIds) {
        if (categoryIds.isEmpty()) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "categoryIds는 최소 1개 이상이어야 합니다.");
        }
        for (String categoryId : categoryIds) {
            if (hairCategoryLookupRepository.findByCategoryId(categoryId).isEmpty()) {
                throw new ApiException(ErrorCode.DESIGNER_SPECIALTY_INVALID_CATEGORY, "존재하지 않는 카테고리입니다: " + categoryId);
            }
        }
    }

    private DesignerSpecialtiesResponse.DesignerSpecialtyItem toItem(HairCategoryLookupRepository.HairCategoryInfo category) {
        return new DesignerSpecialtiesResponse.DesignerSpecialtyItem(
                category.categoryId(),
                category.categoryName());
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private void verifyApprovedDesigner(UserAccount userAccount) {
        if (userAccount.grade() != 2) {
            throw new ApiException(ErrorCode.DESIGNER_SPECIALTY_FORBIDDEN);
        }
    }
}
