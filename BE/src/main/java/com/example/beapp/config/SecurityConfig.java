package com.example.beapp.config;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.AuthenticationEntryPoint;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.AccessDeniedHandler;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import com.example.beapp.common.api.ApiErrorResponse;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.security.JwtAuthenticationFilter;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.http.HttpServletResponse;

@Configuration
@EnableWebSecurity
@EnableConfigurationProperties({
        AppSecurityProperties.class,
        AppCorsProperties.class,
        AppHairProperties.class,
        AppCameraAiProperties.class,
        AppNaverGeocodingProperties.class,
        AppInferenceProperties.class,
        AppGoogleSecurityProperties.class
})
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ObjectMapper objectMapper;
    private final AppCorsProperties appCorsProperties;

    public SecurityConfig(
            JwtAuthenticationFilter jwtAuthenticationFilter,
            ObjectMapper objectMapper,
            AppCorsProperties appCorsProperties) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
        this.objectMapper = objectMapper;
        this.appCorsProperties = appCorsProperties;
    }

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(AbstractHttpConfigurer::disable)
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/error").permitAll()
                        .requestMatchers("/api/health", "/api/*/health", "/actuator/health", "/actuator/info").permitAll()
                        .requestMatchers("/api/swagger-ui.html", "/api/swagger-ui/**", "/api/v3/api-docs/**").permitAll()
                        .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()
                        .requestMatchers(HttpMethod.POST,
                                "/api/internal/hairs/sync",
                                "/api/internal/hairs/sync/",
                                "/api/accounts/google-login",
                                "/api/accounts/google-login/",
                                "/api/accounts/signup",
                                "/api/accounts/signup/",
                                "/api/accounts/login",
                                "/api/accounts/login/",
                                "/api/accounts/logout",
                                "/api/accounts/logout/",
                                "/api/accounts/signout",
                                "/api/accounts/signout/",
                                "/api/accounts/refreshToken",
                                "/api/accounts/refreshToken/").permitAll()
                        .requestMatchers(HttpMethod.GET,
                                "/api/hairs",
                                "/api/hairs/",
                                "/api/hairs/*",
                                "/api/hairs/*/*").permitAll()
                        .requestMatchers(
                                "/api/home/customrank",
                                "/api/home/customrank/",
                                "/api/mypage/**").authenticated()
                        .requestMatchers(HttpMethod.GET,
                                "/api/home/normalrank",
                                "/api/home/normalrank/",
                                "/api/home/categorylist",
                                "/api/home/categorylist/",
                                "/api/home/categorycardlist",
                                "/api/home/categorycardlist/").permitAll()
                        .requestMatchers(HttpMethod.POST,
                                "/api/camera/ai-upgrade",
                                "/api/camera/ai-upgrade/").authenticated()
                        .requestMatchers(HttpMethod.POST,
                                "/api/home/hairclick",
                                "/api/home/hairclick/").authenticated()
                        .requestMatchers(HttpMethod.POST,
                                "/api/home/hairapplybootstrap",
                                "/api/home/hairapplybootstrap/",
                                "/api/home/hairapplyresume",
                                "/api/home/hairapplyresume/",
                                "/api/home/recodehair",
                                "/api/home/recodehair/").permitAll()
                        .requestMatchers(
                                HttpMethod.POST,
                                "/api/hairs/*/like",
                                "/api/hairs/*/like/").authenticated()
                        .requestMatchers(
                                HttpMethod.DELETE,
                                "/api/hairs/*/like",
                                "/api/hairs/*/like/").authenticated()
                        .anyRequest().denyAll())
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint(authenticationEntryPoint())
                        .accessDeniedHandler(accessDeniedHandler()))
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(appCorsProperties.allowedOrigins());
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("Authorization", "Content-Type", "Accept", "Origin", "Cache-Control"));
        configuration.setExposedHeaders(List.of("Authorization", "Location"));
        configuration.setAllowCredentials(true);
        configuration.setMaxAge(Duration.ofHours(1).getSeconds());

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    private AuthenticationEntryPoint authenticationEntryPoint() {
        return (request, response, authException) ->
                writeErrorResponse(response, ErrorCode.UNAUTHORIZED, request.getRequestURI(), ErrorCode.UNAUTHORIZED.getMessage());
    }

    private AccessDeniedHandler accessDeniedHandler() {
        return (request, response, accessDeniedException) ->
                writeErrorResponse(response, ErrorCode.UNAUTHORIZED, request.getRequestURI(), "접근 권한이 없습니다.");
    }

    private void writeErrorResponse(HttpServletResponse response, ErrorCode errorCode, String path, String message) throws java.io.IOException {
        response.setStatus(errorCode.getHttpStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        objectMapper.writeValue(response.getWriter(), ApiErrorResponse.of(errorCode.getCode(), message, List.of(), path));
    }
}
