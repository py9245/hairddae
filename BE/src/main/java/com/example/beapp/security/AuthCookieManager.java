package com.example.beapp.security;

import java.time.Duration;

import org.springframework.http.ResponseCookie;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import com.example.beapp.config.AppSecurityProperties;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;

@Component
public class AuthCookieManager {

    public static final String ACCESS_TOKEN_COOKIE = "accessToken";
    public static final String REFRESH_TOKEN_COOKIE = "refreshToken";

    private static final String ACCESS_TOKEN_PATH = "/";
    private static final String REFRESH_TOKEN_PATH = "/api/accounts";

    private final AppSecurityProperties appSecurityProperties;

    public AuthCookieManager(AppSecurityProperties appSecurityProperties) {
        this.appSecurityProperties = appSecurityProperties;
    }

    public ResponseCookie accessTokenCookie(String accessToken) {
        return buildCookie(
                ACCESS_TOKEN_COOKIE,
                accessToken,
                ACCESS_TOKEN_PATH,
                Duration.ofMinutes(appSecurityProperties.accessTokenExpiryMinutes()));
    }

    public ResponseCookie clearAccessTokenCookie() {
        return clearCookie(ACCESS_TOKEN_COOKIE, ACCESS_TOKEN_PATH);
    }

    public ResponseCookie refreshTokenCookie(String refreshToken) {
        return buildCookie(
                REFRESH_TOKEN_COOKIE,
                refreshToken,
                REFRESH_TOKEN_PATH,
                Duration.ofDays(appSecurityProperties.refreshTokenExpiryDays()));
    }

    public ResponseCookie clearRefreshTokenCookie() {
        return clearCookie(REFRESH_TOKEN_COOKIE, REFRESH_TOKEN_PATH);
    }

    public String getCookieValue(HttpServletRequest request, String cookieName) {
        if (request == null || !StringUtils.hasText(cookieName) || request.getCookies() == null) {
            return null;
        }

        for (Cookie cookie : request.getCookies()) {
            if (cookieName.equals(cookie.getName()) && StringUtils.hasText(cookie.getValue())) {
                return cookie.getValue();
            }
        }

        return null;
    }

    private ResponseCookie clearCookie(String name, String path) {
        return buildCookie(name, "", path, Duration.ZERO);
    }

    private ResponseCookie buildCookie(String name, String value, String path, Duration maxAge) {
        return ResponseCookie.from(name, value)
                .httpOnly(true)
                .secure(true)
                .sameSite("Strict")
                .path(path)
                .maxAge(maxAge)
                .build();
    }
}
