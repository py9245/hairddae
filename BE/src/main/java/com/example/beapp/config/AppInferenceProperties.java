package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.inference")
public record AppInferenceProperties(
        String wsBaseUrl,
        String wsAuthTransport,
        String wsProtocol,
        String audience,
        String nodeId,
        long connectTicketExpirySeconds,
        long processedTimeoutMs,
        long heartbeatIntervalMs,
        long idleTtlMs,
        int featureSchemaVersion,
        int assetBundleSchemaVersion,
        String transformVersion
) {
}
