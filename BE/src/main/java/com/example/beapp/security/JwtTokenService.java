package com.example.beapp.security;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.UUID;

import javax.crypto.SecretKey;

import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppSecurityProperties;
import com.example.beapp.repository.TokenBlocklistRepository;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

@Service
public class JwtTokenService {

    private static final String TOKEN_TYPE_CLAIM = "tokenType";

    private final SecretKey secretKey;
    private final AppSecurityProperties appSecurityProperties;
    private final TokenBlocklistRepository tokenBlocklistRepository;

    public JwtTokenService(AppSecurityProperties appSecurityProperties, TokenBlocklistRepository tokenBlocklistRepository) {
        this.appSecurityProperties = appSecurityProperties;
        this.tokenBlocklistRepository = tokenBlocklistRepository;
        this.secretKey = Keys.hmacShaKeyFor(appSecurityProperties.secret().getBytes(StandardCharsets.UTF_8));
    }

    public String issueAccessToken(String userId) {
        return issueToken(userId, JwtTokenType.ACCESS, Instant.now().plus(appSecurityProperties.accessTokenExpiryMinutes(), ChronoUnit.MINUTES));
    }

    public String issueRefreshToken(String userId) {
        return issueToken(userId, JwtTokenType.REFRESH, Instant.now().plus(appSecurityProperties.refreshTokenExpiryDays(), ChronoUnit.DAYS));
    }

    public TokenPrincipal validateAccessToken(String token) {
        return validateToken(token, JwtTokenType.ACCESS);
    }

    public TokenPrincipal validateRefreshToken(String token) {
        return validateToken(token, JwtTokenType.REFRESH);
    }

    public String extractBearerToken(String authorizationHeader) {
        if (!StringUtils.hasText(authorizationHeader) || !authorizationHeader.startsWith("Bearer ")) {
            return null;
        }
        return authorizationHeader.substring(7);
    }

    public Instant extractExpiration(String token) {
        return validateTokenWithoutType(token).expiresAt();
    }

    public void blockToken(String token) {
        tokenBlocklistRepository.block(token, extractExpiration(token));
    }

    private String issueToken(String userId, JwtTokenType tokenType, Instant expiresAt) {
        Instant now = Instant.now();
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .subject(userId)
                .issuer(appSecurityProperties.issuer())
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiresAt))
                .claim(TOKEN_TYPE_CLAIM, tokenType.name())
                .signWith(secretKey)
                .compact();
    }

    private TokenPrincipal validateToken(String token, JwtTokenType expectedType) {
        TokenPrincipal tokenPrincipal = validateTokenWithoutType(token);
        if (tokenPrincipal.tokenType() != expectedType) {
            throw new ApiException(ErrorCode.INVALID_TOKEN, "토큰 타입이 올바르지 않습니다.");
        }
        return tokenPrincipal;
    }

    private TokenPrincipal validateTokenWithoutType(String token) {
        if (!StringUtils.hasText(token)) {
            throw new ApiException(ErrorCode.INVALID_TOKEN);
        }

        if (tokenBlocklistRepository.isBlocked(token)) {
            throw new ApiException(ErrorCode.INVALID_TOKEN, "폐기된 토큰입니다.");
        }

        try {
            Claims claims = Jwts.parser()
                    .verifyWith(secretKey)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            String userId = claims.getSubject();
            String tokenType = claims.get(TOKEN_TYPE_CLAIM, String.class);
            Date expiration = claims.getExpiration();

            if (!StringUtils.hasText(userId) || !StringUtils.hasText(tokenType) || expiration == null) {
                throw new ApiException(ErrorCode.INVALID_TOKEN);
            }

            return new TokenPrincipal(userId, JwtTokenType.valueOf(tokenType), expiration.toInstant());
        } catch (JwtException | IllegalArgumentException exception) {
            throw new ApiException(ErrorCode.INVALID_TOKEN);
        }
    }

    public record TokenPrincipal(String userId, JwtTokenType tokenType, Instant expiresAt) {
    }
}
