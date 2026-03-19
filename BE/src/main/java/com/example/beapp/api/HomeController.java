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

import com.example.beapp.api.dto.home.CustomRankResponse;
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
@SecurityRequirement(name = "bearerAuth")
public class HomeController {

    private final HomeService homeService;

    public HomeController(HomeService homeService) {
        this.homeService = homeService;
    }

    @GetMapping("/customrank")
    public ResponseEntity<CustomRankResponse> customRank(
            Authentication authentication,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(required = false) String ageCategory,
            @RequestParam(required = false) Integer gender) {
        return ResponseEntity.ok(homeService.getCustomRank(authentication.getName(), ageCategory, gender, size));
    }

    @GetMapping("/nomalrank")
    public ResponseEntity<NormalRankResponse> normalRank(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(500) int size,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String sort) {
        return ResponseEntity.ok(homeService.getNormalRank(category, sort, size));
    }

    @PostMapping({"/hairapplybootstrap", "/hairapplybootstrap/", "/hairapplystart-v2", "/hairapplystart-v2/"})
    public ResponseEntity<HairApplyV2Response> hairApplyBootstrap(
            Authentication authentication,
            @Valid @RequestBody HairApplyStartV2Request request) {
        return ResponseEntity.ok(homeService.startHairApplyV2(request, authentication.getName()));
    }

    @PostMapping({"/hairapplyresume", "/hairapplyresume/", "/hairapplyresume-v2", "/hairapplyresume-v2/"})
    public ResponseEntity<HairApplyV2Response> hairApplyResume(
            Authentication authentication,
            @Valid @RequestBody HairApplyResumeV2Request request) {
        return ResponseEntity.ok(homeService.resumeHairApplyV2(request, authentication.getName()));
    }

    @PostMapping("/recodehair")
    public ResponseEntity<RecodeHairResponse> recodeHair(
            Authentication authentication,
            @Valid @RequestBody RecodeHairRequest request) {
        return ResponseEntity.ok(homeService.recordHair(request, authentication.getName()));
    }
}
