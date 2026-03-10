package com.example.beapp.api;

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

    public AccountsController(AccountsService accountsService) {
        this.accountsService = accountsService;
    }

    @PostMapping({"/login", "/login/"})
    public ResponseEntity<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return ResponseEntity.ok(accountsService.login(request));
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
    public ResponseEntity<SimpleResponse> logout(@Valid @RequestBody LogoutRequest request) {
        return ResponseEntity.ok(accountsService.logout(request));
    }

    @PostMapping({"/signout", "/signout/"})
    public ResponseEntity<SimpleResponse> signout(@Valid @RequestBody SignoutRequest request) {
        return ResponseEntity.ok(accountsService.signout(request));
    }

    @PostMapping({"/refreshToken", "/refreshToken/"})
    public ResponseEntity<TokenRefreshResponse> refresh(@Valid @RequestBody TokenRefreshRequest request) {
        return ResponseEntity.ok(accountsService.refresh(request));
    }
}
