package com.example.beapp.api.dto.home;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HairApplyV2Response(
        int code,
        String message,
        boolean success,
        @JsonProperty("apply_session_id") String applySessionId,
        @JsonProperty("feature_schema_version") int featureSchemaVersion,
        @JsonProperty("transform_version") String transformVersion,
        InferenceConnection inference,
        RtcConnection rtc,
        @JsonProperty("static")
        StaticBootstrap staticInfo
) {
    public static HairApplyV2Response ok(
            String applySessionId,
            int featureSchemaVersion,
            String transformVersion,
            InferenceConnection inference,
            RtcConnection rtc,
            StaticBootstrap staticInfo) {
        return new HairApplyV2Response(
                200,
                "시작 성공",
                true,
                applySessionId,
                featureSchemaVersion,
                transformVersion,
                inference,
                rtc,
                staticInfo);
    }

    public record InferenceConnection(
            @JsonProperty("ws_url") String wsUrl,
            @JsonProperty("ws_auth_transport") String wsAuthTransport,
            @JsonProperty("connect_ticket") String connectTicket,
            @JsonProperty("expires_at") Instant expiresAt,
            @JsonProperty("node_id") String nodeId,
            @JsonProperty("processed_timeout_ms") long processedTimeoutMs,
            @JsonProperty("heartbeat_interval_ms") long heartbeatIntervalMs,
            @JsonProperty("idle_ttl_ms") long idleTtlMs
    ) {
    }

    public record RtcConnection(
            boolean enabled,
            @JsonProperty("offer_url") String offerUrl,
            @JsonProperty("connect_ticket") String connectTicket,
            @JsonProperty("expires_at") Instant expiresAt,
            @JsonProperty("ice_servers") List<IceServer> iceServers
    ) {
    }

    public record IceServer(
            List<String> urls,
            String username,
            String credential
    ) {
    }

    public record StaticBootstrap(
            @JsonProperty("base_url") String baseUrl,
            @JsonProperty("dataset_code") String datasetCode,
            @JsonProperty("asset_bundle_schema_version") int assetBundleSchemaVersion,
            @JsonProperty("asset_index_url") String assetIndexUrl,
            @JsonProperty("preload_asset_ids") List<String> preloadAssetIds
    ) {
    }
}
