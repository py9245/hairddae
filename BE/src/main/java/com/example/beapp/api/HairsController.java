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
import com.example.beapp.api.dto.hairs.HairLikeResponse;
import com.example.beapp.api.dto.hairs.HairListResponse;
import com.example.beapp.service.HairCatalogService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;

@RestController
@Validated
@Profile("!test")
@RequestMapping("/api/hairs")
public class HairsController {

    private final HairCatalogService hairCatalogService;

    public HairsController(HairCatalogService hairCatalogService) {
        this.hairCatalogService = hairCatalogService;
    }

    @GetMapping({"", "/"})
    public ResponseEntity<HairListResponse> list(
            Authentication authentication,
            @RequestParam(required = false) String category,
            @RequestParam(defaultValue = "recent") String sort) {
        return ResponseEntity.ok(hairCatalogService.getHairList(userId(authentication), category, sort));
    }

    @GetMapping("/{hairId:\\d+}")
    public ResponseEntity<HairDetailResponse> detail(
            Authentication authentication,
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairCatalogService.getHairDetail(userId(authentication), hairId));
    }

    @PostMapping({"/{hairId:\\d+}/like", "/{hairId:\\d+}/like/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<HairLikeResponse> like(
            Authentication authentication,
            @PathVariable Long hairId) {
        return ResponseEntity.ok(hairCatalogService.like(authentication.getName(), hairId));
    }

    @DeleteMapping({"/{hairId:\\d+}/like", "/{hairId:\\d+}/like/"})
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
