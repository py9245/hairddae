package com.example.beapp.security;

import java.util.List;
import java.util.Locale;

import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppGoogleSecurityProperties;

@Component
public class GoogleIdTokenVerifier {

    private static final List<String> ALLOWED_ISSUERS = List.of(
            "https://accounts.google.com",
            "accounts.google.com");

    private final AppGoogleSecurityProperties appGoogleSecurityProperties;
    private final JwtDecoder jwtDecoder;

    public GoogleIdTokenVerifier(AppGoogleSecurityProperties appGoogleSecurityProperties) {
        this.appGoogleSecurityProperties = appGoogleSecurityProperties;

        NimbusJwtDecoder googleJwtDecoder = NimbusJwtDecoder.withJwkSetUri(appGoogleSecurityProperties.jwkSetUri()).build();
        googleJwtDecoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
                JwtValidators.createDefault(),
                audienceValidator(),
                issuerValidator(),
                emailVerifiedValidator()));
        this.jwtDecoder = googleJwtDecoder;
    }

    public GoogleIdentity verify(String idToken) {
        if (!StringUtils.hasText(appGoogleSecurityProperties.clientId())) {
            throw new IllegalStateException("Google client ID is not configured.");
        }

        try {
            Jwt jwt = jwtDecoder.decode(idToken);

            String subject = jwt.getSubject();
            String email = jwt.getClaimAsString("email");

            if (!StringUtils.hasText(subject) || !StringUtils.hasText(email)) {
                throw new ApiException(ErrorCode.INVALID_TOKEN, "구글 사용자 정보가 올바르지 않습니다.");
            }

            return new GoogleIdentity(
                    subject,
                    email.trim().toLowerCase(Locale.ROOT));
        } catch (JwtException exception) {
            throw new ApiException(ErrorCode.INVALID_TOKEN, "유효하지 않은 구글 ID 토큰입니다.");
        }
    }

    private OAuth2TokenValidator<Jwt> audienceValidator() {
        return jwt -> {
            List<String> audience = jwt.getAudience();
            if (audience != null && audience.contains(appGoogleSecurityProperties.clientId())) {
                return OAuth2TokenValidatorResult.success();
            }

            return OAuth2TokenValidatorResult.failure(new OAuth2Error(
                    "invalid_token",
                    "구글 ID 토큰 audience가 올바르지 않습니다.",
                    null));
        };
    }

    private OAuth2TokenValidator<Jwt> issuerValidator() {
        return jwt -> {
            String issuer = jwt.getIssuer() == null ? null : jwt.getIssuer().toString();
            if (issuer != null && ALLOWED_ISSUERS.contains(issuer)) {
                return OAuth2TokenValidatorResult.success();
            }

            return OAuth2TokenValidatorResult.failure(new OAuth2Error(
                    "invalid_token",
                    "구글 ID 토큰 issuer가 올바르지 않습니다.",
                    null));
        };
    }

    private OAuth2TokenValidator<Jwt> emailVerifiedValidator() {
        return jwt -> {
            Object emailVerified = jwt.getClaims().get("email_verified");
            boolean verified = emailVerified instanceof Boolean booleanValue
                    ? booleanValue
                    : emailVerified instanceof String stringValue && Boolean.parseBoolean(stringValue);

            if (verified) {
                return OAuth2TokenValidatorResult.success();
            }

            return OAuth2TokenValidatorResult.failure(new OAuth2Error(
                    "invalid_token",
                    "이메일 인증이 완료된 구글 계정만 허용됩니다.",
                    null));
        };
    }

    public record GoogleIdentity(
            String subject,
            String email
    ) {
    }
}
