package com.example.beapp.api;

import java.time.Instant;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.HealthResponse;

@RestController
@RequestMapping("/api/home")
public class HomeHealthController {

    @GetMapping("/health")
    public HealthResponse health() {
        return new HealthResponse("home", "ok", Instant.now());
    }
}
