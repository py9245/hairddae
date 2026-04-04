package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.naver-geocoding")
public record AppNaverGeocodingProperties(
        boolean enabled,
        String baseUrl,
        String apiKeyId,
        String apiKey,
        long requestTimeoutMs
) {
}
