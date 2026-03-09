package com.example.beapp.api;

import java.time.Instant;
import java.util.UUID;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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

import jakarta.validation.Valid;

@RestController
@RequestMapping({"/api/accounts", "/accounts"})
@Validated
public class AccountsController {

    @PostMapping({"/login", "/login/"})
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(LoginResponse.ok(request.userID(), issueAccessToken(), issueRefreshToken()));
    }

    @PostMapping({"/signin", "/signin/"})
    public ResponseEntity<SignupResponse> signup(@Valid @RequestBody SignupRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(SignupResponse.created(request.userID()));
    }

    @PostMapping({"/logout", "/logout/"})
    public ResponseEntity<SimpleResponse> logout(@Valid @RequestBody LogoutRequest request) {
        return ResponseEntity.ok(SimpleResponse.ok("로그아웃 완료"));
    }

    @PostMapping({"/signout", "/signout/"})
    public ResponseEntity<SimpleResponse> signout(@Valid @RequestBody SignoutRequest request) {
        return ResponseEntity.ok(SimpleResponse.ok("회원탈퇴 완료"));
    }

    @PostMapping({"/refreshToken", "/refreshToken/"})
    public ResponseEntity<TokenRefreshResponse> refresh(@Valid @RequestBody TokenRefreshRequest request) {
        String newAccess = issueAccessToken();
        String newRefresh = request.rotate() != null && request.rotate() ? issueRefreshToken() : request.refreshToken();
        return ResponseEntity.ok(TokenRefreshResponse.ok(newAccess, newRefresh));
    }

    private String issueAccessToken() {
        return "access-" + UUID.randomUUID() + "-" + Instant.now().toEpochMilli();
    }

    private String issueRefreshToken() {
        return "refresh-" + UUID.randomUUID() + "-" + Instant.now().toEpochMilli();
    }
}
