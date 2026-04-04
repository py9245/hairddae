package com.example.beapp.service;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.api.dto.mypage.LikeListResponse;
import com.example.beapp.api.dto.mypage.MeResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.SampleHairRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class MypageService {

    private final UserAccountRepository userAccountRepository;
    private final SampleHairRepository sampleHairRepository;
    private final HairCatalogService hairCatalogService;

    public MypageService(
            UserAccountRepository userAccountRepository,
            SampleHairRepository sampleHairRepository,
            ObjectProvider<HairCatalogService> hairCatalogServiceProvider) {
        this.userAccountRepository = userAccountRepository;
        this.sampleHairRepository = sampleHairRepository;
        this.hairCatalogService = hairCatalogServiceProvider.getIfAvailable();
    }

    public HairListResponse getRecent(String userId) {
        verifyUserExists(userId);
        if (hairCatalogService != null) {
            return hairCatalogService.getAppliedList(userId);
        }

        var recentCards = sampleHairRepository.findRecentCards();
        return HairListResponse.ok(recentCards.size(), recentCards);
    }

    public MeResponse getUser(String userId) {
        UserAccount userAccount = getRequiredUser(userId);
        return MeResponse.ok(userAccount.userID(), userAccount.birthDate(), userAccount.gender(), userAccount.grade());
    }

    public LikeListResponse getLikeList(String userId) {
        verifyUserExists(userId);
        return LikeListResponse.ok(
                userId,
                hairCatalogService != null
                        ? hairCatalogService.getLikeCards(userId)
                        : sampleHairRepository.findLikeCards());
    }

    private void verifyUserExists(String userId) {
        getRequiredUser(userId);
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }
}
