package com.example.beapp.security;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.UUID;

import javax.crypto.SecretKey;

import org.springframework.stereotype.Service;

import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.config.AppSecurityProperties;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.MacAlgorithm;
import io.jsonwebtoken.security.Keys;

@Service
public class InferenceConnectTicketService {

    private static final String TOKEN_TYPE = "INFERENCE_CONNECT";
    private static final MacAlgorithm CONNECT_TICKET_ALGORITHM = Jwts.SIG.HS256;

    private final SecretKey secretKey;
    private final AppInferenceProperties appInferenceProperties;
    private final AppSecurityProperties appSecurityProperties;

    public InferenceConnectTicketService(
            AppInferenceProperties appInferenceProperties,
            AppSecurityProperties appSecurityProperties) {
        this.appInferenceProperties = appInferenceProperties;
        this.appSecurityProperties = appSecurityProperties;
        this.secretKey = Keys.hmacShaKeyFor(appSecurityProperties.secret().getBytes(StandardCharsets.UTF_8));
    }

    public IssuedInferenceTicket issueConnectTicket(
            String userId,
            String applySessionId,
            String deviceId,
            Integer hairId,
            String datasetCode,
            String representativeAssetId) {
        Instant issuedAt = Instant.now();
        Instant expiresAt = issuedAt.plus(appInferenceProperties.connectTicketExpirySeconds(), ChronoUnit.SECONDS);
        String token = Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(userId)
                .issuer(appSecurityProperties.issuer())
                .issuedAt(Date.from(issuedAt))
                .notBefore(Date.from(issuedAt))
                .expiration(Date.from(expiresAt))
                .claim("aud", appInferenceProperties.audience())
                .claim("tokenType", TOKEN_TYPE)
                .claim("sid", applySessionId)
                .claim("did", deviceId)
                .claim("hid", hairId)
                .claim("node", appInferenceProperties.nodeId())
                .claim("ver", appInferenceProperties.featureSchemaVersion())
                .claim("schema_version", appInferenceProperties.featureSchemaVersion())
                .claim("single_use", Boolean.TRUE)
                .claim("dataset_code", datasetCode)
                .claim("representative_asset_id", representativeAssetId)
                .signWith(secretKey, CONNECT_TICKET_ALGORITHM)
                .compact();
        return new IssuedInferenceTicket(token, expiresAt);
    }

    public record IssuedInferenceTicket(
            String token,
            Instant expiresAt
    ) {
    }
}
