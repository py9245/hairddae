package com.example.beapp.service;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.accounts.LoginRequest;
import com.example.beapp.api.dto.accounts.LoginResponse;
import com.example.beapp.api.dto.accounts.LogoutRequest;
import com.example.beapp.api.dto.accounts.SignoutRequest;
import com.example.beapp.api.dto.accounts.SignupRequest;
import com.example.beapp.api.dto.accounts.SignupResponse;
import com.example.beapp.api.dto.accounts.SimpleResponse;
import com.example.beapp.api.dto.accounts.TokenRefreshRequest;
import com.example.beapp.api.dto.accounts.TokenRefreshResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.JwtTokenService;

@Service
public class AccountsService {

    private final UserAccountRepository userAccountRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenService jwtTokenService;

    public AccountsService(
            UserAccountRepository userAccountRepository,
            PasswordEncoder passwordEncoder,
            JwtTokenService jwtTokenService) {
        this.userAccountRepository = userAccountRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenService = jwtTokenService;
    }

    public LoginResponse login(LoginRequest request) {
        UserAccount userAccount = userAccountRepository.findByUserId(request.userID())
                .orElseThrow(() -> new ApiException(ErrorCode.INVALID_CREDENTIALS));

        if (!passwordEncoder.matches(request.password(), userAccount.encodedPassword())) {
            throw new ApiException(ErrorCode.INVALID_CREDENTIALS);
        }

        return LoginResponse.ok(
                userAccount.userID(),
                jwtTokenService.issueAccessToken(userAccount.userID()),
                jwtTokenService.issueRefreshToken(userAccount.userID()));
    }

    public SignupResponse signup(SignupRequest request) {
        if (userAccountRepository.existsByUserId(request.userID())) {
            throw new ApiException(ErrorCode.DUPLICATE_USER);
        }

        userAccountRepository.save(new UserAccount(
                request.userID(),
                passwordEncoder.encode(request.password()),
                request.age(),
                request.gender()));

        return SignupResponse.created(request.userID());
    }

    public SimpleResponse logout(LogoutRequest request) {
        jwtTokenService.validateAccessToken(request.accessToken());
        jwtTokenService.blockToken(request.accessToken());

        if (StringUtils.hasText(request.refreshToken())) {
            jwtTokenService.validateRefreshToken(request.refreshToken());
            jwtTokenService.blockToken(request.refreshToken());
        }

        return SimpleResponse.ok("로그아웃 완료");
    }

    public SimpleResponse signout(SignoutRequest request) {
        String userId = jwtTokenService.validateAccessToken(request.accessToken()).userId();
        if (!userAccountRepository.existsByUserId(userId)) {
            throw new ApiException(ErrorCode.USER_NOT_FOUND);
        }

        jwtTokenService.blockToken(request.accessToken());
        userAccountRepository.deleteByUserId(userId);
        return SimpleResponse.ok("회원탈퇴 완료");
    }

    public TokenRefreshResponse refresh(TokenRefreshRequest request) {
        String userId = jwtTokenService.validateRefreshToken(request.refreshToken()).userId();
        boolean rotate = request.rotate() == null || request.rotate();

        String newAccessToken = jwtTokenService.issueAccessToken(userId);
        String newRefreshToken = rotate ? jwtTokenService.issueRefreshToken(userId) : request.refreshToken();

        if (rotate) {
            jwtTokenService.blockToken(request.refreshToken());
        }

        return TokenRefreshResponse.ok(newAccessToken, newRefreshToken);
    }
}
