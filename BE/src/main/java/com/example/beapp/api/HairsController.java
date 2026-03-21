package com.example.beapp.api;

import org.springframework.context.annotation.Profile;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.hairs.HairDetailResponse;
import com.example.beapp.api.dto.hairs.HairAssetIndexV2Response;
import com.example.beapp.api.dto.hairs.HairLikeResponse;
import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.api.dto.hairs.HairRecommendResponse;
import com.example.beapp.service.HairAssetBundleIndexService;
import com.example.beapp.service.HairCatalogService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

@RestController
@Validated
@Profile("!test")
@RequestMapping("/api/hairs")
public class HairsController {

    private final HairCatalogService hairCatalogService;
    private final HairAssetBundleIndexService hairAssetBundleIndexService;

    public HairsController(
            HairCatalogService hairCatalogService,
            HairAssetBundleIndexService hairAssetBundleIndexService) {
        this.hairCatalogService = hairCatalogService;
        this.hairAssetBundleIndexService = hairAssetBundleIndexService;
    }

    @GetMapping({"", "/"})
    public ResponseEntity<HairListResponse> list(
            Authentication authentication,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(required = false) String category,
            @RequestParam(defaultValue = "recent") String sort) {
        return ResponseEntity.ok(hairCatalogService.getHairList(userId(authentication), page, size, category, sort));
    }

    @GetMapping({"/cameralist", "/cameralist/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<HairListResponse> cameraList(
            Authentication authentication,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size) {
        return ResponseEntity.ok(hairCatalogService.getCameraList(authentication.getName(), page, size));
    }

    @GetMapping("/recommend")
    public ResponseEntity<HairRecommendResponse> recommend(
            @RequestParam(required = false) Long hairId,
            @RequestParam(required = false) Integer yaw1deg,
            @RequestParam(required = false) Integer pitch1deg,
            @RequestParam(required = false) Integer roll1deg) {
        return ResponseEntity.ok(hairCatalogService.recommend(hairId, yaw1deg, pitch1deg, roll1deg));
    }

    @GetMapping("/{hairId}/asset-index")
    public ResponseEntity<HairAssetIndexV2Response> assetIndexV2(
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairAssetBundleIndexService.getAssetIndex(hairId));
    }

    @GetMapping("/{hairId}")
    public ResponseEntity<HairDetailResponse> detail(
            Authentication authentication,
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairCatalogService.getHairDetail(userId(authentication), hairId));
    }

    @PostMapping({"/{hairId}/like", "/{hairId}/like/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<HairLikeResponse> like(
            Authentication authentication,
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairCatalogService.like(authentication.getName(), hairId));
    }

    @DeleteMapping({"/{hairId}/like", "/{hairId}/like/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<HairLikeResponse> unlike(
            Authentication authentication,
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairCatalogService.unlike(authentication.getName(), hairId));
    }

    private String userId(Authentication authentication) {
        return authentication == null ? null : authentication.getName();
    }
}
