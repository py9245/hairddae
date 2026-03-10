package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyRequest;
import com.example.beapp.api.dto.home.HairApplyResponse;
import com.example.beapp.api.dto.home.HairApplyStatusResponse;
import com.example.beapp.api.dto.home.NormalRankResponse;
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
        return ResponseEntity.ok(homeService.getCustomRank(authentication.getName(), ageCategory, gender));
    }

    @GetMapping("/nomalrank")
    public ResponseEntity<NormalRankResponse> normalRank(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(500) int size,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String sort) {
        return ResponseEntity.ok(homeService.getNormalRank());
    }

    @PostMapping("/hairapplystart")
    public ResponseEntity<HairApplyResponse> hairApplyStart(
            @RequestHeader(name = "Authorization", required = false) String authorization,
            @Valid @RequestBody HairApplyRequest request) {
        return ResponseEntity.ok(homeService.startHairApply(request, authorization));
    }

    @GetMapping("/hairapplystatus/{applySessionId}")
    public ResponseEntity<HairApplyStatusResponse> hairApplyStatus(
            Authentication authentication,
            @PathVariable String applySessionId) {
        return ResponseEntity.ok(homeService.getHairApplyStatus(authentication.getName(), applySessionId));
    }
}
