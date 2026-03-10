package com.example.beapp.repository;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.util.StringUtils;

@Repository
public class TokenBlocklistRepository {

    private static final String KEY_PREFIX = "auth:blocklist:";

    private final StringRedisTemplate stringRedisTemplate;
    private final Map<String, Instant> blockedTokens = new ConcurrentHashMap<>();

    public TokenBlocklistRepository(ObjectProvider<StringRedisTemplate> stringRedisTemplateProvider) {
        this.stringRedisTemplate = stringRedisTemplateProvider.getIfAvailable();
    }

    public void block(String token, Instant expiresAt) {
        if (!StringUtils.hasText(token) || expiresAt == null) {
            return;
        }

        Duration ttl = Duration.between(Instant.now(), expiresAt);
        if (ttl.isZero() || ttl.isNegative()) {
            return;
        }

        if (stringRedisTemplate != null) {
            stringRedisTemplate.opsForValue().set(key(token), "1", ttl);
            return;
        }

        blockedTokens.put(token, expiresAt);
    }

    public boolean isBlocked(String token) {
        if (!StringUtils.hasText(token)) {
            return false;
        }

        if (stringRedisTemplate != null) {
            return Boolean.TRUE.equals(stringRedisTemplate.hasKey(key(token)));
        }

        purgeExpired();
        return blockedTokens.containsKey(token);
    }

    private void purgeExpired() {
        Instant now = Instant.now();
        blockedTokens.entrySet().removeIf(entry -> entry.getValue().isBefore(now));
    }

    private String key(String token) {
        return KEY_PREFIX + token;
    }
}
