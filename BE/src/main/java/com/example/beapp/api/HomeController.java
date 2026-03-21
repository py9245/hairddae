package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.home.CategoryCardListResponse;
import com.example.beapp.api.dto.home.CategoryListResponse;
import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairClickRequest;
import com.example.beapp.api.dto.home.HairClickResponse;
import com.example.beapp.api.dto.home.HairApplyResumeV2Request;
import com.example.beapp.api.dto.home.HairApplyStartV2Request;
import com.example.beapp.api.dto.home.HairApplyV2Response;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.api.dto.home.RecodeHairRequest;
import com.example.beapp.api.dto.home.RecodeHairResponse;
import com.example.beapp.service.HomeService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

@RestController
@RequestMapping("/api/home")
@Validated
public class HomeController {

    private final HomeService homeService;

    public HomeController(HomeService homeService) {
        this.homeService = homeService;
    }

    @GetMapping("/customrank")
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<CustomRankResponse> customRank(
            Authentication authentication,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return ResponseEntity.ok(homeService.getCustomRank(authentication.getName(), size));
    }

    @GetMapping({"/normalrank", "/normalrank/"})
    public ResponseEntity<NormalRankResponse> normalRank(
            Authentication authentication,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return ResponseEntity.ok(homeService.getNormalRank(userId(authentication), size));
    }

    @GetMapping({"/categorylist", "/categorylist/"})
    public ResponseEntity<CategoryListResponse> categoryList() {
        return ResponseEntity.ok(homeService.getCategoryList());
    }

    @GetMapping({"/categorycardlist", "/categorycardlist/"})
    public ResponseEntity<CategoryCardListResponse> categoryCardList(
            Authentication authentication,
            @RequestParam(required = false) String categoryId,
            @RequestParam(defaultValue = "50") @Min(1) @Max(500) int size) {
        return ResponseEntity.ok(homeService.getCategoryCardList(userId(authentication), categoryId, size));
    }

    @PostMapping({"/hairapplybootstrap", "/hairapplybootstrap/"})
    public ResponseEntity<HairApplyV2Response> hairApplyBootstrap(
            Authentication authentication,
            @Valid @RequestBody HairApplyStartV2Request request) {
        return ResponseEntity.ok(homeService.startHairApplyV2(request, resolveCameraUserId(authentication, request.deviceId())));
    }

    @PostMapping({"/hairapplyresume", "/hairapplyresume/"})
    public ResponseEntity<HairApplyV2Response> hairApplyResume(
            Authentication authentication,
            @Valid @RequestBody HairApplyResumeV2Request request) {
        return ResponseEntity.ok(homeService.resumeHairApplyV2(request, resolveCameraUserId(authentication, request.deviceId())));
    }

    @PostMapping("/recodehair")
    public ResponseEntity<RecodeHairResponse> recodeHair(
            Authentication authentication,
            @Valid @RequestBody RecodeHairRequest request) {
        if (authentication == null || authentication.getName() == null) {
            return ResponseEntity.ok(RecodeHairResponse.ok());
        }
        return ResponseEntity.ok(homeService.recordHair(request, authentication.getName()));
    }

    @PostMapping({"/hairclick", "/hairclick/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<HairClickResponse> hairClick(
            Authentication authentication,
            @Valid @RequestBody HairClickRequest request) {
        return ResponseEntity.ok(homeService.recordAppliedHair(request, authentication.getName()));
    }

    private String resolveCameraUserId(Authentication authentication, String deviceId) {
        if (authentication != null && authentication.getName() != null) {
            return authentication.getName();
        }
        return "anon:%s".formatted(deviceId);
    }

    private String userId(Authentication authentication) {
        return authentication == null ? null : authentication.getName();
    }
}
