package com.example.beapp.websocket;

import java.util.List;
import java.util.Map;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.http.server.ServletServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.security.AuthCookieManager;
import com.example.beapp.security.JwtTokenService;

import jakarta.servlet.http.HttpServletRequest;

@Component
public class AccessTokenHandshakeInterceptor implements HandshakeInterceptor {

    public static final String ATTR_USER_ID = "authenticatedUserId";
    public static final String ATTR_ACCESS_TOKEN_EXPIRES_AT = "authenticatedAccessTokenExpiresAt";

    private final JwtTokenService jwtTokenService;
    private final AuthCookieManager authCookieManager;

    public AccessTokenHandshakeInterceptor(
            JwtTokenService jwtTokenService,
            AuthCookieManager authCookieManager) {
        this.jwtTokenService = jwtTokenService;
        this.authCookieManager = authCookieManager;
    }

    @Override
    public boolean beforeHandshake(
            ServerHttpRequest request,
            ServerHttpResponse response,
            WebSocketHandler wsHandler,
            Map<String, Object> attributes) throws Exception {
        String accessToken = resolveAccessToken(request);
        if (!StringUtils.hasText(accessToken)) {
            return true;
        }

        try {
            JwtTokenService.TokenPrincipal tokenPrincipal = jwtTokenService.validateAccessToken(accessToken);
            attributes.put(ATTR_USER_ID, tokenPrincipal.userId());
            attributes.put(ATTR_ACCESS_TOKEN_EXPIRES_AT, tokenPrincipal.expiresAt());
            return true;
        } catch (ApiException exception) {
            response.setStatusCode(HttpStatus.UNAUTHORIZED);
            return false;
        }
    }

    @Override
    public void afterHandshake(
            ServerHttpRequest request,
            ServerHttpResponse response,
            WebSocketHandler wsHandler,
            Exception exception) {
    }

    private String resolveAccessToken(ServerHttpRequest request) {
        if (request instanceof ServletServerHttpRequest servletRequest) {
            HttpServletRequest httpServletRequest = servletRequest.getServletRequest();
            String bearerToken = jwtTokenService.extractBearerToken(httpServletRequest.getHeader(HttpHeaders.AUTHORIZATION));
            if (StringUtils.hasText(bearerToken)) {
                return bearerToken;
            }
            return authCookieManager.getCookieValue(httpServletRequest, AuthCookieManager.ACCESS_TOKEN_COOKIE);
        }

        List<String> authorizationHeaders = request.getHeaders().get(HttpHeaders.AUTHORIZATION);
        if (authorizationHeaders == null || authorizationHeaders.isEmpty()) {
            return null;
        }
        return jwtTokenService.extractBearerToken(authorizationHeaders.get(0));
    }
}
