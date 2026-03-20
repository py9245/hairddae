package com.example.beapp.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistration;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

import com.example.beapp.websocket.AccessTokenHandshakeInterceptor;
import com.example.beapp.websocket.HairApplyWebSocketHandler;
import com.example.beapp.websocket.HairRecommendWebSocketHandler;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final HairApplyWebSocketHandler hairApplyWebSocketHandler;
    private final HairRecommendWebSocketHandler hairRecommendWebSocketHandler;
    private final AppCorsProperties appCorsProperties;
    private final AccessTokenHandshakeInterceptor accessTokenHandshakeInterceptor;

    public WebSocketConfig(
            HairApplyWebSocketHandler hairApplyWebSocketHandler,
            HairRecommendWebSocketHandler hairRecommendWebSocketHandler,
            AppCorsProperties appCorsProperties,
            AccessTokenHandshakeInterceptor accessTokenHandshakeInterceptor) {
        this.hairApplyWebSocketHandler = hairApplyWebSocketHandler;
        this.hairRecommendWebSocketHandler = hairRecommendWebSocketHandler;
        this.appCorsProperties = appCorsProperties;
        this.accessTokenHandshakeInterceptor = accessTokenHandshakeInterceptor;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        WebSocketHandlerRegistration hairApplyRegistration = registry.addHandler(
                hairApplyWebSocketHandler,
                "/home/hairapply",
                "/home/hairapply/");
        hairApplyRegistration.addInterceptors(accessTokenHandshakeInterceptor);
        applyAllowedOrigins(hairApplyRegistration);

        WebSocketHandlerRegistration hairRecommendRegistration = registry.addHandler(
                hairRecommendWebSocketHandler,
                "/api/hairs/recommend/ws",
                "/api/hairs/recommend/ws/");
        applyAllowedOrigins(hairRecommendRegistration);
    }

    private void applyAllowedOrigins(WebSocketHandlerRegistration registration) {
        if (appCorsProperties.allowedOrigins().isEmpty()) {
            registration.setAllowedOriginPatterns("*");
            return;
        }
        registration.setAllowedOrigins(appCorsProperties.allowedOrigins().toArray(String[]::new));
    }
}
