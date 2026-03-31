package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.kakao-local")
public record AppKakaoLocalProperties(
        boolean enabled,
        String baseUrl,
        String restApiKey,
        long requestTimeoutMs
) {
}
