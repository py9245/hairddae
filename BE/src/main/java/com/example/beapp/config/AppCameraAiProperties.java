package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.camera-ai")
public record AppCameraAiProperties(
        boolean enabled,
        String providerBaseUrl,
        String providerAuthToken,
        String modelName,
        long requestTimeoutMs,
        long maxUploadSizeBytes,
        String resultDir,
        String size,
        String quality,
        String outputFormat,
        String inputFidelity
) {
}
