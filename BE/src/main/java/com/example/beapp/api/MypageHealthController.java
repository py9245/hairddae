package com.example.beapp.api;

import java.time.Instant;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.HealthResponse;

@RestController
@RequestMapping("/api/mypage")
public class MypageHealthController {

    @GetMapping("/health")
    public HealthResponse health() {
        return new HealthResponse("mypage", "ok", Instant.now());
    }
}
