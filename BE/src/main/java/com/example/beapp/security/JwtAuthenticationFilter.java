package com.example.beapp.security;

import java.io.IOException;
import java.util.List;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import com.example.beapp.common.exception.ApiException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Component
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenService jwtTokenService;
    private final AuthCookieManager authCookieManager;

    public JwtAuthenticationFilter(
            JwtTokenService jwtTokenService,
            AuthCookieManager authCookieManager) {
        this.jwtTokenService = jwtTokenService;
        this.authCookieManager = authCookieManager;
    }

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {
        String authorizationHeader = request.getHeader("Authorization");
        String bearerToken = jwtTokenService.extractBearerToken(authorizationHeader);
        String accessToken = StringUtils.hasText(bearerToken)
                ? bearerToken
                : authCookieManager.getCookieValue(request, AuthCookieManager.ACCESS_TOKEN_COOKIE);

        if (!StringUtils.hasText(accessToken)) {
            filterChain.doFilter(request, response);
            return;
        }

        try {
            JwtTokenService.TokenPrincipal tokenPrincipal = jwtTokenService.validateAccessToken(accessToken);
            UsernamePasswordAuthenticationToken authentication = UsernamePasswordAuthenticationToken.authenticated(
                    tokenPrincipal.userId(),
                    accessToken,
                    List.of(new SimpleGrantedAuthority("ROLE_USER")));
            SecurityContextHolder.getContext().setAuthentication(authentication);
            filterChain.doFilter(request, response);
        } catch (ApiException exception) {
            SecurityContextHolder.clearContext();
            filterChain.doFilter(request, response);
        }
    }
}
