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
public class RefreshTokenRepository {

    private static final String KEY_PREFIX = "auth:refresh:";

    private final StringRedisTemplate stringRedisTemplate;
    private final Map<String, StoredRefreshToken> storedTokens = new ConcurrentHashMap<>();

    public RefreshTokenRepository(ObjectProvider<StringRedisTemplate> stringRedisTemplateProvider) {
        this.stringRedisTemplate = stringRedisTemplateProvider.getIfAvailable();
    }

    public void save(String userId, String refreshToken, Instant expiresAt) {
        if (!StringUtils.hasText(userId) || !StringUtils.hasText(refreshToken) || expiresAt == null) {
            return;
        }

        Duration ttl = Duration.between(Instant.now(), expiresAt);
        if (ttl.isZero() || ttl.isNegative()) {
            return;
        }

        if (stringRedisTemplate != null) {
            stringRedisTemplate.opsForValue().set(key(userId), refreshToken, ttl);
            return;
        }

        storedTokens.put(userId, new StoredRefreshToken(refreshToken, expiresAt));
    }

    public boolean matches(String userId, String refreshToken) {
        if (!StringUtils.hasText(userId) || !StringUtils.hasText(refreshToken)) {
            return false;
        }

        if (stringRedisTemplate != null) {
            String storedRefreshToken = stringRedisTemplate.opsForValue().get(key(userId));
            return refreshToken.equals(storedRefreshToken);
        }

        purgeExpired();
        StoredRefreshToken storedRefreshToken = storedTokens.get(userId);
        return storedRefreshToken != null && refreshToken.equals(storedRefreshToken.token());
    }

    public void delete(String userId) {
        if (!StringUtils.hasText(userId)) {
            return;
        }

        if (stringRedisTemplate != null) {
            stringRedisTemplate.delete(key(userId));
            return;
        }

        storedTokens.remove(userId);
    }

    private void purgeExpired() {
        Instant now = Instant.now();
        storedTokens.entrySet().removeIf(entry -> entry.getValue().expiresAt().isBefore(now));
    }

    private String key(String userId) {
        return KEY_PREFIX + userId;
    }

    private record StoredRefreshToken(String token, Instant expiresAt) {
    }
}
