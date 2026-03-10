package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.security.jwt")
public record AppSecurityProperties(
        String secret,
        long accessTokenExpiryMinutes,
        long refreshTokenExpiryDays,
        String issuer
) {
}
