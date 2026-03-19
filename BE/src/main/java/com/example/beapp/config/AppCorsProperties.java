package com.example.beapp.config;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;

@ConfigurationProperties(prefix = "app.security.cors")
public record AppCorsProperties(
        List<String> allowedOrigins
) {
    public AppCorsProperties {
        allowedOrigins = allowedOrigins == null
                ? List.of()
                : allowedOrigins.stream()
                        .filter(StringUtils::hasText)
                        .map(String::trim)
                        .toList();
    }
}
