package com.example.beapp.api;

import java.time.Instant;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.HealthResponse;

@RestController
@RequestMapping("/api/accounts")
public class AccountsHealthController {

    @GetMapping("/health")
    public HealthResponse health() {
        return new HealthResponse("accounts", "ok", Instant.now());
    }
}
