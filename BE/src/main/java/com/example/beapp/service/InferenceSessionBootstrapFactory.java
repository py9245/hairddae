package com.example.beapp.service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.home.HairApplyV2Response;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.security.InferenceConnectTicketService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class InferenceSessionBootstrapFactory {

    private final InferenceConnectTicketService inferenceConnectTicketService;
    private final AppInferenceProperties appInferenceProperties;
    private final List<HairApplyV2Response.IceServer> rtcIceServers;

    public InferenceSessionBootstrapFactory(
            InferenceConnectTicketService inferenceConnectTicketService,
            AppInferenceProperties appInferenceProperties,
            ObjectMapper objectMapper) {
        this.inferenceConnectTicketService = inferenceConnectTicketService;
        this.appInferenceProperties = appInferenceProperties;
        this.rtcIceServers = parseRtcIceServers(objectMapper, appInferenceProperties.rtcIceServersJson());
    }

    public InferenceConnectTicketService.IssuedInferenceTicket issueConnectTicket(
            String userId,
            String applySessionId,
            String deviceId,
            Integer hairId,
            String datasetCode,
            String representativeAssetId) {
        return inferenceConnectTicketService.issueConnectTicket(
                userId,
                applySessionId,
                deviceId,
                hairId,
                datasetCode,
                representativeAssetId);
    }

    public int featureSchemaVersion() {
        return appInferenceProperties.featureSchemaVersion();
    }

    public int assetBundleSchemaVersion() {
        return appInferenceProperties.assetBundleSchemaVersion();
    }

    public String transformVersion() {
        return appInferenceProperties.transformVersion();
    }

    public HairApplyV2Response.InferenceConnection buildInferenceConnection(
            InferenceConnectTicketService.IssuedInferenceTicket ticket) {
        return new HairApplyV2Response.InferenceConnection(
                appInferenceProperties.wsBaseUrl(),
                appInferenceProperties.wsAuthTransport(),
                ticket.token(),
                ticket.expiresAt(),
                appInferenceProperties.nodeId(),
                appInferenceProperties.processedTimeoutMs(),
                appInferenceProperties.heartbeatIntervalMs(),
                appInferenceProperties.idleTtlMs());
    }

    public HairApplyV2Response.RtcConnection buildRtcConnection(
            InferenceConnectTicketService.IssuedInferenceTicket ticket) {
        return new HairApplyV2Response.RtcConnection(
                StringUtils.hasText(appInferenceProperties.rtcOfferUrl()),
                appInferenceProperties.rtcOfferUrl(),
                ticket.token(),
                ticket.expiresAt(),
                rtcIceServers);
    }

    private List<HairApplyV2Response.IceServer> parseRtcIceServers(ObjectMapper objectMapper, String rawJson) {
        if (!StringUtils.hasText(rawJson)) {
            return List.of();
        }

        try {
            JsonNode payload = objectMapper.readTree(rawJson);
            if (!payload.isArray()) {
                throw new IllegalStateException("RTC ICE 서버 설정 형식이 올바르지 않습니다.");
            }

            List<HairApplyV2Response.IceServer> iceServers = new ArrayList<>();
            for (JsonNode item : payload) {
                JsonNode urlsNode = item.path("urls");
                if (!urlsNode.isArray() || urlsNode.isEmpty()) {
                    continue;
                }

                List<String> urls = new ArrayList<>();
                for (JsonNode urlNode : urlsNode) {
                    if (urlNode.isTextual() && StringUtils.hasText(urlNode.asText())) {
                        urls.add(urlNode.asText());
                    }
                }
                if (urls.isEmpty()) {
                    continue;
                }

                String username = item.path("username").isTextual() ? item.path("username").asText() : null;
                String credential = item.path("credential").isTextual() ? item.path("credential").asText() : null;
                iceServers.add(new HairApplyV2Response.IceServer(urls, username, credential));
            }

            return List.copyOf(iceServers);
        } catch (IOException exception) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "RTC ICE 서버 설정을 읽지 못했습니다.");
        }
    }
}
