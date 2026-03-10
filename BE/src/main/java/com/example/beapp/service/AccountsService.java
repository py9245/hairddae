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

    public LoginResponse login(LoginRequest request) {
        UserAccount userAccount = userAccountRepository.findByUserId(request.userID())
                .orElseThrow(() -> new ApiException(ErrorCode.INVALID_CREDENTIALS));

        if (!passwordEncoder.matches(request.password(), userAccount.encodedPassword())) {
            throw new ApiException(ErrorCode.INVALID_CREDENTIALS);
        }

        return LoginResponse.ok(
                userAccount.userID(),
                jwtTokenService.issueAccessToken(userAccount.userID()),
                issueAndStoreRefreshToken(userAccount.userID()));
    }

    public SignupResponse signup(SignupRequest request) {
        if (userAccountRepository.existsByUserId(request.userID())) {
            throw new ApiException(ErrorCode.DUPLICATE_USER, "이미 사용 중인 아이디입니다.");
        }

        if (!request.password().equals(request.passwordConfirm())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "비밀번호 확인이 일치하지 않습니다.");
        }

        userAccountRepository.save(new UserAccount(
                request.userID(),
                passwordEncoder.encode(request.password()),
                request.age(),
                request.gender()));

        return SignupResponse.created(request.userID());
    }

    public SimpleResponse logout(LogoutRequest request) {
        String userId = jwtTokenService.validateAccessToken(request.accessToken()).userId();
        jwtTokenService.blockToken(request.accessToken());

        if (StringUtils.hasText(request.refreshToken())) {
            JwtTokenService.TokenPrincipal refreshTokenPrincipal = validateStoredRefreshToken(request.refreshToken());
            if (!userId.equals(refreshTokenPrincipal.userId())) {
                throw new ApiException(ErrorCode.INVALID_TOKEN, "사용자와 일치하지 않는 리프레시 토큰입니다.");
            }
            jwtTokenService.blockToken(request.refreshToken());
        }

        refreshTokenRepository.delete(userId);
        return SimpleResponse.ok("로그아웃 완료");
    }

    public SimpleResponse signout(SignoutRequest request) {
        String userId = jwtTokenService.validateAccessToken(request.accessToken()).userId();
        if (!userAccountRepository.existsByUserId(userId)) {
            throw new ApiException(ErrorCode.USER_NOT_FOUND);
        }

        jwtTokenService.blockToken(request.accessToken());
        refreshTokenRepository.delete(userId);
        userAccountRepository.deleteByUserId(userId);
        return SimpleResponse.ok("회원탈퇴 완료");
    }

    public TokenRefreshResponse refresh(TokenRefreshRequest request) {
        String userId = validateStoredRefreshToken(request.refreshToken()).userId();
        boolean rotate = request.rotate() == null || request.rotate();

        String newAccessToken = jwtTokenService.issueAccessToken(userId);
        String newRefreshToken = rotate ? issueAndStoreRefreshToken(userId) : request.refreshToken();

        if (rotate) {
            jwtTokenService.blockToken(request.refreshToken());
        }

        return TokenRefreshResponse.ok(newAccessToken, newRefreshToken);
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
}
