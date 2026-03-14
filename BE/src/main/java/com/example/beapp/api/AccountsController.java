package com.example.beapp.api;

import java.time.Duration;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.CookieValue;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.accounts.LoginRequest;
import com.example.beapp.api.dto.accounts.LoginResponse;
import com.example.beapp.api.dto.accounts.LogoutRequest;
import com.example.beapp.api.dto.accounts.SignoutRequest;
import com.example.beapp.api.dto.accounts.SignupRequest;
import com.example.beapp.api.dto.accounts.SignupResponse;
import com.example.beapp.api.dto.accounts.SimpleResponse;
import com.example.beapp.api.dto.accounts.TokenRefreshRequest;
import com.example.beapp.api.dto.accounts.TokenRefreshResponse;
import com.example.beapp.service.AccountsService;

import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/accounts")
@Validated
public class AccountsController {

    private static final String REFRESH_TOKEN_COOKIE = "refreshToken";
    private static final Duration REFRESH_COOKIE_MAX_AGE = Duration.ofDays(14);

    private final AccountsService accountsService;

    public AccountsController(AccountsService accountsService) {
        this.accountsService = accountsService;
    }

    @PostMapping({"/login", "/login/"})
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        AccountsService.AuthTokens authTokens = accountsService.login(request);
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, refreshTokenCookie(authTokens.refreshToken()).toString())
                .body(LoginResponse.ok(authTokens.userId(), authTokens.accessToken()));
    }

    @PostMapping({"/signin", "/signin/"})
    @ApiResponses({
            @ApiResponse(
                    responseCode = "201",
                    description = "Created",
                    content = @Content(schema = @Schema(implementation = SignupResponse.class)))
    })
    public ResponseEntity<SignupResponse> signup(@Valid @RequestBody SignupRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(accountsService.signup(request));
    }

    @PostMapping({"/logout", "/logout/"})
    public ResponseEntity<SimpleResponse> logout(
            @RequestHeader(name = HttpHeaders.AUTHORIZATION, required = false) String authorization,
            @CookieValue(name = REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @Valid @RequestBody(required = false) LogoutRequest request) {
        String accessToken = extractAccessToken(authorization);
        LogoutRequest payload = request == null ? new LogoutRequest(false) : request;
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, clearRefreshTokenCookie().toString())
                .body(accountsService.logout(accessToken, refreshToken, payload));
    }

    @PostMapping({"/signout", "/signout/"})
    public ResponseEntity<SimpleResponse> signout(
            @RequestHeader(name = HttpHeaders.AUTHORIZATION, required = false) String authorization,
            @CookieValue(name = REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @Valid @RequestBody(required = false) SignoutRequest request) {
        String accessToken = extractAccessToken(authorization);
        SignoutRequest payload = request == null ? new SignoutRequest(null, null) : request;
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, clearRefreshTokenCookie().toString())
                .body(accountsService.signout(accessToken, refreshToken, payload));
    }

    @PostMapping({"/refreshToken", "/refreshToken/"})
    public ResponseEntity<TokenRefreshResponse> refresh(
            @CookieValue(name = REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @RequestBody(required = false) TokenRefreshRequest request) {
        TokenRefreshRequest payload = request == null ? new TokenRefreshRequest(true) : request;
        AccountsService.AuthTokens authTokens = accountsService.refresh(refreshToken, payload);
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, refreshTokenCookie(authTokens.refreshToken()).toString())
                .body(TokenRefreshResponse.ok(authTokens.accessToken()));
    }

    private String extractAccessToken(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            return null;
        }
        return authorization.substring(7);
    }

    private ResponseCookie refreshTokenCookie(String refreshToken) {
        return ResponseCookie.from(REFRESH_TOKEN_COOKIE, refreshToken)
                .httpOnly(true)
                .secure(true)
                .sameSite("Strict")
                .path("/api/accounts")
                .maxAge(REFRESH_COOKIE_MAX_AGE)
                .build();
    }

    private ResponseCookie clearRefreshTokenCookie() {
        return ResponseCookie.from(REFRESH_TOKEN_COOKIE, "")
                .httpOnly(true)
                .secure(true)
                .sameSite("Strict")
                .path("/api/accounts")
                .maxAge(Duration.ZERO)
                .build();
    }
}
