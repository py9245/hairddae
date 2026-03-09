package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.mypage.BookmarkResponse;
import com.example.beapp.api.dto.mypage.RecentResponse;
import com.example.beapp.api.dto.mypage.UserIdResponse;
import com.example.beapp.service.MypageService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

@RestController
@RequestMapping("/api/mypage")
@Validated
@SecurityRequirement(name = "bearerAuth")
public class MypageController {

    private final MypageService mypageService;

    public MypageController(MypageService mypageService) {
        this.mypageService = mypageService;
    }

    @GetMapping("/recent")
    public ResponseEntity<RecentResponse> recent(
            Authentication authentication,
            @RequestParam(defaultValue = "5") @Min(1) @Max(600) int minViewSec,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(defaultValue = "recent") String sort) {
        return ResponseEntity.ok(mypageService.getRecent(authentication.getName()));
    }

    @GetMapping("/user")
    public ResponseEntity<UserIdResponse> user(
            Authentication authentication) {
        return ResponseEntity.ok(mypageService.getUser(authentication.getName()));
    }

    @GetMapping("/bookmarklist")
    public ResponseEntity<BookmarkResponse> bookmarks(
            Authentication authentication,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(defaultValue = "recent") String sort,
            @RequestParam(defaultValue = "false") boolean onlyActive) {
        return ResponseEntity.ok(mypageService.getBookmarks(authentication.getName()));
    }
}
