package com.example.beapp.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistration;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

import com.example.beapp.websocket.AccessTokenHandshakeInterceptor;
import com.example.beapp.websocket.HairApplyWebSocketHandler;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final HairApplyWebSocketHandler hairApplyWebSocketHandler;
    private final AppCorsProperties appCorsProperties;
    private final AccessTokenHandshakeInterceptor accessTokenHandshakeInterceptor;

    public WebSocketConfig(
            HairApplyWebSocketHandler hairApplyWebSocketHandler,
            AppCorsProperties appCorsProperties,
            AccessTokenHandshakeInterceptor accessTokenHandshakeInterceptor) {
        this.hairApplyWebSocketHandler = hairApplyWebSocketHandler;
        this.appCorsProperties = appCorsProperties;
        this.accessTokenHandshakeInterceptor = accessTokenHandshakeInterceptor;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        WebSocketHandlerRegistration registration = registry.addHandler(
                hairApplyWebSocketHandler,
                "/api/home/hairapply",
                "/api/home/hairapply/");
        registration.addInterceptors(accessTokenHandshakeInterceptor);

        if (appCorsProperties.allowedOrigins().isEmpty()) {
            registration.setAllowedOriginPatterns("*");
            return;
        }

        registration.setAllowedOrigins(appCorsProperties.allowedOrigins().toArray(String[]::new));
    }
}
