package com.example.beapp.config;

import java.nio.charset.StandardCharsets;
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

import com.example.beapp.common.api.ApiErrorResponse;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.security.JwtAuthenticationFilter;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.http.HttpServletResponse;

@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(AppSecurityProperties.class)
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ObjectMapper objectMapper;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter, ObjectMapper objectMapper) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
        this.objectMapper = objectMapper;
    }

    @Bean
    SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/error").permitAll()
                        .requestMatchers("/api/health", "/api/*/health", "/actuator/health", "/actuator/info").permitAll()
                        .requestMatchers("/api/swagger-ui.html", "/api/swagger-ui/**", "/api/v3/api-docs/**").permitAll()
                        .requestMatchers(HttpMethod.POST,
                                "/api/accounts/login",
                                "/api/accounts/login/",
                                "/api/accounts/signin",
                                "/api/accounts/signin/",
                                "/api/accounts/logout",
                                "/api/accounts/logout/",
                                "/api/accounts/signout",
                                "/api/accounts/signout/",
                                "/api/accounts/refreshToken",
                                "/api/accounts/refreshToken/",
                                "/api/home/hairapplystart",
                                "/api/home/hairapplystart/").permitAll()
                        .requestMatchers(
                                "/api/home/customrank",
                                "/api/home/customrank/",
                                "/api/home/nomalrank",
                                "/api/home/nomalrank/",
                                "/api/mypage/**").authenticated()
                        .anyRequest().permitAll())
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
