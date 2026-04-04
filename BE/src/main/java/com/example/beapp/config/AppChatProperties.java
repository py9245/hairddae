package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.chat")
public record AppChatProperties(
        long maxUploadSizeBytes,
        String storageDir
) {
}
