package com.example.beapp.api;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
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
import com.example.beapp.security.AuthCookieManager;
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

    private final AccountsService accountsService;
    private final AuthCookieManager authCookieManager;

    public AccountsController(AccountsService accountsService, AuthCookieManager authCookieManager) {
        this.accountsService = accountsService;
        this.authCookieManager = authCookieManager;
    }

    @PostMapping({"/login", "/login/"})
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        AccountsService.AuthTokens authTokens = accountsService.login(request);
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, authCookieManager.accessTokenCookie(authTokens.accessToken()).toString())
                .header(HttpHeaders.SET_COOKIE, authCookieManager.refreshTokenCookie(authTokens.refreshToken()).toString())
                .body(LoginResponse.ok(authTokens.userId()));
    }

    @PostMapping({"/signup", "/signup/"})
    @ApiResponses({
            @ApiResponse(
                    responseCode = "201",
                    description = "Created",
                    content = @Content(schema = @Schema(implementation = SignupResponse.class)))
    })
    public ResponseEntity<SignupResponse> signup(@Valid @RequestBody SignupRequest request) {
        AccountsService.AuthTokens authTokens = accountsService.signup(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, authCookieManager.accessTokenCookie(authTokens.accessToken()).toString())
                .header(HttpHeaders.SET_COOKIE, authCookieManager.refreshTokenCookie(authTokens.refreshToken()).toString())
                .body(SignupResponse.created(authTokens.userId()));
    }

    @PostMapping({"/logout", "/logout/"})
    public ResponseEntity<SimpleResponse> logout(
            @RequestHeader(name = HttpHeaders.AUTHORIZATION, required = false) String authorization,
            @CookieValue(name = AuthCookieManager.ACCESS_TOKEN_COOKIE, required = false) String accessTokenCookie,
            @CookieValue(name = AuthCookieManager.REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @Valid @RequestBody(required = false) LogoutRequest request) {
        String accessToken = extractAccessToken(authorization, accessTokenCookie);
        LogoutRequest payload = request == null ? new LogoutRequest(false) : request;
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, authCookieManager.clearAccessTokenCookie().toString())
                .header(HttpHeaders.SET_COOKIE, authCookieManager.clearRefreshTokenCookie().toString())
                .body(accountsService.logout(accessToken, refreshToken, payload));
    }

    @PostMapping({"/signout", "/signout/"})
    public ResponseEntity<SimpleResponse> signout(
            @RequestHeader(name = HttpHeaders.AUTHORIZATION, required = false) String authorization,
            @CookieValue(name = AuthCookieManager.ACCESS_TOKEN_COOKIE, required = false) String accessTokenCookie,
            @CookieValue(name = AuthCookieManager.REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @Valid @RequestBody(required = false) SignoutRequest request) {
        String accessToken = extractAccessToken(authorization, accessTokenCookie);
        SignoutRequest payload = request == null ? new SignoutRequest(null, null) : request;
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, authCookieManager.clearAccessTokenCookie().toString())
                .header(HttpHeaders.SET_COOKIE, authCookieManager.clearRefreshTokenCookie().toString())
                .body(accountsService.signout(accessToken, refreshToken, payload));
    }

    @PostMapping({"/refreshToken", "/refreshToken/"})
    public ResponseEntity<TokenRefreshResponse> refresh(
            @CookieValue(name = AuthCookieManager.REFRESH_TOKEN_COOKIE, required = false) String refreshToken,
            @RequestBody(required = false) TokenRefreshRequest request) {
        TokenRefreshRequest payload = request == null ? new TokenRefreshRequest(true) : request;
        AccountsService.AuthTokens authTokens = accountsService.refresh(refreshToken, payload);
        return ResponseEntity.ok()
                .header(HttpHeaders.CACHE_CONTROL, "no-store")
                .header(HttpHeaders.SET_COOKIE, authCookieManager.accessTokenCookie(authTokens.accessToken()).toString())
                .header(HttpHeaders.SET_COOKIE, authCookieManager.refreshTokenCookie(authTokens.refreshToken()).toString())
                .body(TokenRefreshResponse.ok());
    }

    private String extractAccessToken(String authorization, String accessTokenCookie) {
        if (authorization != null && authorization.startsWith("Bearer ")) {
            return authorization.substring(7);
        }
        return accessTokenCookie;
    }
}
