package com.example.beapp.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import javax.crypto.SecretKey;

import org.junit.jupiter.api.Test;

import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.config.AppSecurityProperties;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

class InferenceConnectTicketServiceTests {

    @Test
    void issuesConnectTicketWithExpectedAlgorithmNodeAndSchemaClaims() throws Exception {
        String secret = "hairddae-test-jwt-secret-key-for-local-tests-2026";
        AppInferenceProperties inferenceProperties = new AppInferenceProperties(
                "/ws/inference/apply",
                "/rtc/inference/offer",
                "[]",
                "test-sync-secret",
                "sec-websocket-protocol.v1",
                "inference",
                "infer-gpu-01",
                30,
                250,
                5000,
                30000,
                2,
                1,
                "affine_v1");
        AppSecurityProperties securityProperties = new AppSecurityProperties(secret, 60, 1, "hairddae-test");
        InferenceConnectTicketService service = new InferenceConnectTicketService(inferenceProperties, securityProperties);

        var issuedTicket = service.issueConnectTicket(
                "user-1",
                "session-1",
                "device-1",
                1,
                "0001",
                "asset-1");

        SecretKey secretKey = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        Claims claims = Jwts.parser()
                .verifyWith(secretKey)
                .build()
                .parseSignedClaims(issuedTicket.token())
                .getPayload();
        String[] tokenParts = issuedTicket.token().split("\\.");
        ObjectMapper objectMapper = new ObjectMapper();
        String headerJson = new String(Base64.getUrlDecoder().decode(tokenParts[0]), StandardCharsets.UTF_8);
        JsonNode header = objectMapper.readTree(headerJson);

        assertEquals("HS256", header.path("alg").asText());
        assertEquals("INFERENCE_CONNECT", claims.get("tokenType", String.class));
        assertEquals("session-1", claims.get("sid", String.class));
        assertEquals("device-1", claims.get("did", String.class));
        assertEquals(1, claims.get("hid", Integer.class));
        assertEquals("infer-gpu-01", claims.get("node", String.class));
        assertEquals(2, claims.get("ver", Integer.class));
        assertEquals(2, claims.get("schema_version", Integer.class));
        assertEquals(true, claims.get("single_use", Boolean.class));
        assertEquals("0001", claims.get("dataset_code", String.class));
        assertEquals("asset-1", claims.get("representative_asset_id", String.class));
        assertTrue(claims.getExpiration().toInstant().isAfter(claims.getIssuedAt().toInstant()));
    }
}
