package com.example.beapp.repository;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Repository;

@Repository
public class TokenBlocklistRepository {

    private final Map<String, Instant> blockedTokens = new ConcurrentHashMap<>();

    public void block(String token, Instant expiresAt) {
        blockedTokens.put(token, expiresAt);
    }

    public boolean isBlocked(String token) {
        purgeExpired();
        return blockedTokens.containsKey(token);
    }

    private void purgeExpired() {
        Instant now = Instant.now();
        blockedTokens.entrySet().removeIf(entry -> entry.getValue().isBefore(now));
    }
}
