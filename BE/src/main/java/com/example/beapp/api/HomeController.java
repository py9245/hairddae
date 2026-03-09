package com.example.beapp.api;

import java.time.OffsetDateTime;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.HairItem;
import com.example.beapp.api.dto.home.CustomRankResponse;
import com.example.beapp.api.dto.home.HairApplyRequest;
import com.example.beapp.api.dto.home.NormalRankResponse;
import com.example.beapp.api.dto.accounts.SimpleResponse;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;

@RestController
@RequestMapping({"/api/home", "/home"})
@Validated
public class HomeController {

    @GetMapping("/customrank")
    public ResponseEntity<CustomRankResponse> customRank(
            @RequestHeader(name = "Authorization", required = false) String authorization,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(required = false) String ageCategory,
            @RequestParam(required = false) Integer gender) {
        List<HairItem> list = List.of(sampleHair(301), sampleHair(302));
        return ResponseEntity.ok(CustomRankResponse.ok(resolveUser(authorization), gender, 25, ageCategory == null ? "25_29" : ageCategory, list));
    }

    @GetMapping("/nomalrank")
    public ResponseEntity<NormalRankResponse> normalRank(
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "50") @Min(1) @Max(500) int size,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) String sort) {
        List<HairItem> list = List.of(sampleHair(401), sampleHair(402), sampleHair(403));
        return ResponseEntity.ok(NormalRankResponse.ok(4000, list));
    }

    @PostMapping("/hairapplystart")
    public ResponseEntity<SimpleResponse> hairApplyStart(@Valid @RequestBody HairApplyRequest request) {
        return ResponseEntity.ok(SimpleResponse.ok("스타일 적용 시작 기록 완료"));
    }

    private HairItem sampleHair(int id) {
        return new HairItem(
                id,
                "short",
                "/static/hairs/%d/preview.png".formatted(id),
                12,
                3,
                OffsetDateTime.now().minusDays(2));
    }

    private String resolveUser(String authorization) {
        if (authorization != null && authorization.startsWith("Bearer ")) {
            return "tokenUser";
        }
        return "TestUser01";
    }
}
