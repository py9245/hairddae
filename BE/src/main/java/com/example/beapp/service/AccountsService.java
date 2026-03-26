package com.example.beapp.service;

import java.util.UUID;

import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.accounts.GoogleLoginRequest;
import com.example.beapp.api.dto.accounts.LoginRequest;
import com.example.beapp.api.dto.accounts.LogoutRequest;
import com.example.beapp.api.dto.accounts.SignoutRequest;
import com.example.beapp.api.dto.accounts.SignupRequest;
import com.example.beapp.api.dto.accounts.SimpleResponse;
import com.example.beapp.api.dto.accounts.TokenRefreshRequest;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.LoginType;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.RefreshTokenRepository;
import com.example.beapp.repository.UserAccountRepository;
import com.example.beapp.security.JwtTokenService;

@Service
public class AccountsService {

    private final UserAccountRepository userAccountRepository;
    private final RefreshTokenRepository refreshTokenRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenService jwtTokenService;

    public AccountsService(
            UserAccountRepository userAccountRepository,
            RefreshTokenRepository refreshTokenRepository,
            PasswordEncoder passwordEncoder,
            JwtTokenService jwtTokenService) {
        this.userAccountRepository = userAccountRepository;
        this.refreshTokenRepository = refreshTokenRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenService = jwtTokenService;
    }

    public AuthTokens login(LoginRequest request) {
        UserAccount userAccount = userAccountRepository.findByUserId(request.userID())
                .orElseThrow(() -> new ApiException(ErrorCode.INVALID_CREDENTIALS));

        if (!userAccount.loginType().isLocal()) {
            throw new ApiException(ErrorCode.INVALID_CREDENTIALS, "일반 로그인 계정이 아닙니다.");
        }

        if (!passwordEncoder.matches(request.password(), userAccount.encodedPassword())) {
            throw new ApiException(ErrorCode.INVALID_CREDENTIALS);
        }

        return new AuthTokens(
                userAccount.userID(),
                jwtTokenService.issueAccessToken(userAccount.userID()),
                issueAndStoreRefreshToken(userAccount.userID()));
    }

    public AuthTokens googleLogin(GoogleLoginRequest request) {
        String normalizedEmail = request.normalizedEmail();
        UserAccount userAccount = userAccountRepository.findByUserId(normalizedEmail)
                .map(existingUserAccount -> {
                    if (existingUserAccount.loginType() != LoginType.GOOGLE) {
                        throw new ApiException(ErrorCode.DUPLICATE_USER, "이미 일반 로그인으로 가입된 계정입니다.");
                    }
                    return existingUserAccount;
                })
                .orElseGet(() -> userAccountRepository.save(new UserAccount(
                        normalizedEmail,
                        passwordEncoder.encode(UUID.randomUUID().toString()),
                        null,
                        null,
                        LoginType.GOOGLE)));

        return new AuthTokens(
                userAccount.userID(),
                jwtTokenService.issueAccessToken(userAccount.userID()),
                issueAndStoreRefreshToken(userAccount.userID()));
    }

    public AuthTokens signup(SignupRequest request) {
        if (userAccountRepository.existsByUserId(request.userID())) {
            throw new ApiException(ErrorCode.DUPLICATE_USER, "이미 사용 중인 아이디입니다.");
        }

        if (!request.password().equals(request.passwordConfirm())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "비밀번호 확인이 일치하지 않습니다.");
        }

        UserAccount savedUserAccount = userAccountRepository.save(new UserAccount(
                request.userID(),
                passwordEncoder.encode(request.password()),
                request.birthDate(),
                request.gender(),
                LoginType.LOCAL));

        return new AuthTokens(
                savedUserAccount.userID(),
                jwtTokenService.issueAccessToken(savedUserAccount.userID()),
                issueAndStoreRefreshToken(savedUserAccount.userID()));
    }

    public SimpleResponse logout(String accessToken, String refreshToken, LogoutRequest request) {
        String userId = jwtTokenService.validateAccessToken(accessToken).userId();
        jwtTokenService.blockToken(accessToken);

        if (StringUtils.hasText(refreshToken)) {
            JwtTokenService.TokenPrincipal refreshTokenPrincipal = validateStoredRefreshToken(refreshToken);
            if (!userId.equals(refreshTokenPrincipal.userId())) {
                throw new ApiException(ErrorCode.INVALID_TOKEN, "사용자와 일치하지 않는 리프레시 토큰입니다.");
            }
            jwtTokenService.blockToken(refreshToken);
        }

        refreshTokenRepository.delete(userId);
        return SimpleResponse.ok("로그아웃 완료");
    }

    public SimpleResponse signout(String accessToken, String refreshToken, SignoutRequest request) {
        String userId = jwtTokenService.validateAccessToken(accessToken).userId();
        if (!userAccountRepository.existsByUserId(userId)) {
            throw new ApiException(ErrorCode.USER_NOT_FOUND);
        }

        jwtTokenService.blockToken(accessToken);
        if (StringUtils.hasText(refreshToken)) {
            jwtTokenService.blockToken(refreshToken);
        }
        refreshTokenRepository.delete(userId);
        userAccountRepository.deleteByUserId(userId);
        return SimpleResponse.ok("회원탈퇴 완료");
    }

    public AuthTokens refresh(String refreshToken, TokenRefreshRequest request) {
        String userId = validateStoredRefreshToken(refreshToken).userId();
        boolean rotate = request.rotate() == null || request.rotate();

        String newAccessToken = jwtTokenService.issueAccessToken(userId);
        String newRefreshToken = rotate ? issueAndStoreRefreshToken(userId) : refreshToken;

        if (rotate) {
            jwtTokenService.blockToken(refreshToken);
        }

        return new AuthTokens(userId, newAccessToken, newRefreshToken);
    }

    private String issueAndStoreRefreshToken(String userId) {
        String refreshToken = jwtTokenService.issueRefreshToken(userId);
        refreshTokenRepository.save(userId, refreshToken, jwtTokenService.extractExpiration(refreshToken));
        return refreshToken;
    }

    private JwtTokenService.TokenPrincipal validateStoredRefreshToken(String refreshToken) {
        JwtTokenService.TokenPrincipal tokenPrincipal = jwtTokenService.validateRefreshToken(refreshToken);
        if (!refreshTokenRepository.matches(tokenPrincipal.userId(), refreshToken)) {
            throw new ApiException(ErrorCode.INVALID_TOKEN, "저장된 리프레시 토큰이 아닙니다.");
        }
        return tokenPrincipal;
    }

    public record AuthTokens(
            String userId,
            String accessToken,
            String refreshToken
    ) {
    }
}
