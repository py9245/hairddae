package com.example.beapp.api;

import java.time.OffsetDateTime;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.HairItem;
import com.example.beapp.api.dto.mypage.BookmarkResponse;
import com.example.beapp.api.dto.mypage.RecentResponse;
import com.example.beapp.api.dto.mypage.UserIdResponse;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

@RestController
@RequestMapping("/api/mypage")
@Validated
public class MypageController {

    @GetMapping("/recent")
    public ResponseEntity<RecentResponse> recent(
            @RequestHeader(name = "Authorization", required = false) String authorization,
            @RequestParam(defaultValue = "5") @Min(1) @Max(600) int minViewSec,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(defaultValue = "recent") String sort) {
        List<HairItem> list = List.of(sampleHair(101), sampleHair(102));
        return ResponseEntity.ok(RecentResponse.ok(resolveUser(authorization), list));
    }

    @GetMapping("/user")
    public ResponseEntity<UserIdResponse> user(
            @RequestHeader(name = "Authorization", required = false) String authorization) {
        return ResponseEntity.ok(UserIdResponse.ok(resolveUser(authorization)));
    }

    @GetMapping("/bookmarklist")
    public ResponseEntity<BookmarkResponse> bookmarks(
            @RequestHeader(name = "Authorization", required = false) String authorization,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(200) int size,
            @RequestParam(defaultValue = "recent") String sort,
            @RequestParam(defaultValue = "false") boolean onlyActive) {
        List<HairItem> list = List.of(sampleHair(201), sampleHair(202));
        return ResponseEntity.ok(BookmarkResponse.ok(resolveUser(authorization), list));
    }

    private HairItem sampleHair(int id) {
        return new HairItem(
                id,
                "short",
                "/static/hairs/%d/preview.png".formatted(id),
                12,
                3,
                OffsetDateTime.now().minusDays(1));
    }

    private String resolveUser(String authorization) {
        if (authorization != null && authorization.startsWith("Bearer ")) {
            return "tokenUser";
        }
        return "TestUser01";
    }
}
