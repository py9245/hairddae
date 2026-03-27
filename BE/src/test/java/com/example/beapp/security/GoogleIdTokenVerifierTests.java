package com.example.beapp.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppGoogleSecurityProperties;

class GoogleIdTokenVerifierTests {

    @Test
    void verifyRejectsWhenGoogleClientIdIsMissing() {
        GoogleIdTokenVerifier verifier = new GoogleIdTokenVerifier(
                new AppGoogleSecurityProperties("", "https://www.googleapis.com/oauth2/v3/certs"));

        ApiException exception = assertThrows(ApiException.class, () -> verifier.verify("dummy-id-token"));

        assertEquals(ErrorCode.INVALID_REQUEST, exception.getErrorCode());
        assertEquals("APP_SECURITY_GOOGLE_CLIENT_ID 설정이 필요합니다.", exception.getMessage());
    }
}
