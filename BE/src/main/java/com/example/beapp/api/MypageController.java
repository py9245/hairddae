package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.api.dto.mypage.LikeListResponse;
import com.example.beapp.api.dto.mypage.MeResponse;
import com.example.beapp.service.MypageService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;

@RestController
@RequestMapping("/api/mypage")
@Validated
@SecurityRequirement(name = "bearerAuth")
public class MypageController {

    private final MypageService mypageService;

    public MypageController(MypageService mypageService) {
        this.mypageService = mypageService;
    }

    @GetMapping({"/appliedlist", "/appliedlist/"})
    public ResponseEntity<HairListResponse> recent(Authentication authentication) {
        return ResponseEntity.ok(mypageService.getRecent(authentication.getName()));
    }

    @GetMapping({"/user", "/user/"})
    public ResponseEntity<MeResponse> user(
            Authentication authentication) {
        return ResponseEntity.ok(mypageService.getUser(authentication.getName()));
    }

    @GetMapping({"/likelist", "/likelist/"})
    public ResponseEntity<LikeListResponse> likeList(Authentication authentication) {
        return ResponseEntity.ok(mypageService.getLikeList(authentication.getName()));
    }
}
