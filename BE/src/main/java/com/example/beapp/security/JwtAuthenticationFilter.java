package com.example.beapp.security;

import java.io.IOException;
import java.util.List;

import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import com.example.beapp.common.api.ApiErrorResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenService jwtTokenService;
    private final ObjectMapper objectMapper;

    public JwtAuthenticationFilter(JwtTokenService jwtTokenService, ObjectMapper objectMapper) {
        this.jwtTokenService = jwtTokenService;
        this.objectMapper = objectMapper;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        String authorizationHeader = request.getHeader("Authorization");
        String bearerToken = jwtTokenService.extractBearerToken(authorizationHeader);

        if (!StringUtils.hasText(bearerToken)) {
            filterChain.doFilter(request, response);
            return;
        }

        try {
            JwtTokenService.TokenPrincipal tokenPrincipal = jwtTokenService.validateAccessToken(bearerToken);
            UsernamePasswordAuthenticationToken authentication = UsernamePasswordAuthenticationToken.authenticated(
                    tokenPrincipal.userId(),
                    bearerToken,
                    List.of(new SimpleGrantedAuthority("ROLE_USER")));
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
        } catch (ApiException exception) {
            SecurityContextHolder.clearContext();
            writeUnauthorizedResponse(response, request, exception.getMessage());
        }
    }

    private void writeUnauthorizedResponse(HttpServletResponse response, HttpServletRequest request, String message) throws IOException {
        response.setStatus(ErrorCode.INVALID_TOKEN.getHttpStatus().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding("UTF-8");
        objectMapper.writeValue(
                response.getWriter(),
                ApiErrorResponse.of(ErrorCode.INVALID_TOKEN.getCode(), message, List.of(), request.getRequestURI()));
    }
}
