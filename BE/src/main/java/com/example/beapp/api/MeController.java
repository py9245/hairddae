package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.mypage.MeResponse;
import com.example.beapp.service.MypageService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;

@RestController
@RequestMapping("/api")
@SecurityRequirement(name = "bearerAuth")
public class MeController {

    private final MypageService mypageService;

    public MeController(MypageService mypageService) {
        this.mypageService = mypageService;
    }

    @GetMapping({"/me", "/me/"})
    public ResponseEntity<MeResponse> me(Authentication authentication) {
        return ResponseEntity.ok(mypageService.getMe(authentication.getName()));
    }
}
