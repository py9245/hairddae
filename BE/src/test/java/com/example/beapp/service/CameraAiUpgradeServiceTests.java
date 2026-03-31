package com.example.beapp.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDate;
import java.util.Optional;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.mockito.ArgumentCaptor;
import org.springframework.mock.web.MockMultipartFile;

import com.example.beapp.api.dto.camera.CameraAiUpgradeResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppCameraAiProperties;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.UserAccountRepository;

class CameraAiUpgradeServiceTests {

    @TempDir
    Path tempDir;

    @Test
    void upgradeStoresResultImageAndReturnsStaticUrl() throws Exception {
        UserAccountRepository userAccountRepository = mock(UserAccountRepository.class);
        GmsImageGenerationClient gmsImageGenerationClient = mock(GmsImageGenerationClient.class);

        given(userAccountRepository.findByUserId("TestUser01"))
                .willReturn(Optional.of(new UserAccount(
                        "TestUser01",
                        "encoded-password",
                        LocalDate.of(2000, 1, 1),
                        "M")));
        given(gmsImageGenerationClient.generateEditedImage(any(), any(), eq("TestUser01")))
                .willReturn(new GmsImageGenerationClient.GeneratedImage("png-image".getBytes(), "png"));

        CameraAiUpgradeService service = new CameraAiUpgradeService(
                userAccountRepository,
                gmsImageGenerationClient,
                properties(),
                new AppHairProperties(tempDir, "/static"));

        MockMultipartFile image = new MockMultipartFile(
                "image",
                "capture.png",
                "image/png",
                "source-image".getBytes());

        CameraAiUpgradeResponse response = service.upgrade("TestUser01", "browser-device", image);

        assertEquals(200, response.code());
        assertTrue(response.success());
        assertTrue(response.requestId().matches("^[0-9a-f\\-]{36}$"));
        assertEquals("/static/camera-ai/%s/result.png".formatted(response.requestId()), response.resultImageUrl());
        assertTrue(Files.exists(tempDir.resolve("camera-ai").resolve(response.requestId()).resolve("result.png")));

        ArgumentCaptor<String> promptCaptor = ArgumentCaptor.forClass(String.class);
        verify(gmsImageGenerationClient).generateEditedImage(eq(image), promptCaptor.capture(), eq("TestUser01"));
        assertTrue(promptCaptor.getValue().contains("눈썹 아래 영역은 수정하지 마세요."));
    }

    @Test
    void upgradeRejectsUnsupportedImageType() {
        UserAccountRepository userAccountRepository = mock(UserAccountRepository.class);
        GmsImageGenerationClient gmsImageGenerationClient = mock(GmsImageGenerationClient.class);

        given(userAccountRepository.findByUserId("TestUser01"))
                .willReturn(Optional.of(new UserAccount(
                        "TestUser01",
                        "encoded-password",
                        LocalDate.of(2000, 1, 1),
                        "M")));

        CameraAiUpgradeService service = new CameraAiUpgradeService(
                userAccountRepository,
                gmsImageGenerationClient,
                properties(),
                new AppHairProperties(tempDir, "/static"));

        MockMultipartFile image = new MockMultipartFile(
                "image",
                "capture.gif",
                "image/gif",
                "gif-image".getBytes());

        ApiException exception = assertThrows(ApiException.class, () -> service.upgrade("TestUser01", null, image));
        assertEquals(ErrorCode.UNSUPPORTED_IMAGE_TYPE, exception.getErrorCode());
    }

    @Test
    void upgradeRejectsTooLargeFile() {
        UserAccountRepository userAccountRepository = mock(UserAccountRepository.class);
        GmsImageGenerationClient gmsImageGenerationClient = mock(GmsImageGenerationClient.class);

        given(userAccountRepository.findByUserId("TestUser01"))
                .willReturn(Optional.of(new UserAccount(
                        "TestUser01",
                        "encoded-password",
                        LocalDate.of(2000, 1, 1),
                        "M")));

        AppCameraAiProperties properties = new AppCameraAiProperties(
                true,
                "https://gms.example.com/v1",
                "test-key",
                "gpt-image-1-mini",
                30000L,
                4L,
                "camera-ai",
                "1024x1024",
                "low",
                "png",
                "high");

        CameraAiUpgradeService service = new CameraAiUpgradeService(
                userAccountRepository,
                gmsImageGenerationClient,
                properties,
                new AppHairProperties(tempDir, "/static"));

        MockMultipartFile image = new MockMultipartFile(
                "image",
                "capture.png",
                "image/png",
                "too-large".getBytes());

        ApiException exception = assertThrows(ApiException.class, () -> service.upgrade("TestUser01", null, image));
        assertEquals(ErrorCode.FILE_TOO_LARGE, exception.getErrorCode());
    }

    private AppCameraAiProperties properties() {
        return new AppCameraAiProperties(
                true,
                "https://gms.example.com/v1",
                "test-key",
                "gpt-image-1-mini",
                30000L,
                5_242_880L,
                "camera-ai",
                "1024x1024",
                "low",
                "png",
                "high");
    }
}
