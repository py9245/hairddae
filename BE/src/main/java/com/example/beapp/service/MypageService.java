package com.example.beapp.service;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;

import com.example.beapp.api.dto.mypage.BookmarkResponse;
import com.example.beapp.api.dto.mypage.MeResponse;
import com.example.beapp.api.dto.mypage.RecentResponse;
import com.example.beapp.api.dto.mypage.UserIdResponse;
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

    public RecentResponse getRecent(String userId, int minViewSec, int page, int size) {
        verifyUserExists(userId);
        return RecentResponse.ok(
                userId,
                hairCatalogService != null
                        ? hairCatalogService.getRecentItems(userId, minViewSec, page, size)
                        : sampleHairRepository.findRecentItems());
    }

    public MeResponse getMe(String userId) {
        UserAccount userAccount = getRequiredUser(userId);
        return MeResponse.ok(userAccount.userID(), userAccount.birthDate(), userAccount.gender());
    }

    public UserIdResponse getUser(String userId) {
        verifyUserExists(userId);
        return UserIdResponse.ok(userId);
    }

    public BookmarkResponse getBookmarks(String userId, int page, int size, boolean onlyActive) {
        verifyUserExists(userId);
        return BookmarkResponse.ok(
                userId,
                hairCatalogService != null
                        ? hairCatalogService.getBookmarkItems(userId, page, size, onlyActive)
                        : sampleHairRepository.findBookmarkItems());
    }

    private void verifyUserExists(String userId) {
        getRequiredUser(userId);
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }
}
