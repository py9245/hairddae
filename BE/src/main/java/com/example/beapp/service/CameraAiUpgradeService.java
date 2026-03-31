package com.example.beapp.service;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.camera.CameraAiUpgradeResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppCameraAiProperties;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class CameraAiUpgradeService {

    private static final Set<String> ALLOWED_CONTENT_TYPES = Set.of(
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/webp");

    private static final String PROMPT = normalizePrompt("""
            눈썹 아래론 건들지 말고 이마 부분의 경계선 어색한게 있다면 그것만 수정해줘
            """);

    private final UserAccountRepository userAccountRepository;
    private final GmsImageGenerationClient gmsImageGenerationClient;
    private final AppCameraAiProperties appCameraAiProperties;
    private final AppHairProperties appHairProperties;


    public CameraAiUpgradeService(
            UserAccountRepository userAccountRepository,
            GmsImageGenerationClient gmsImageGenerationClient,
            AppCameraAiProperties appCameraAiProperties,
            AppHairProperties appHairProperties) {
        this.userAccountRepository = userAccountRepository;
        this.gmsImageGenerationClient = gmsImageGenerationClient;
        this.appCameraAiProperties = appCameraAiProperties;
        this.appHairProperties = appHairProperties;
    }

    public CameraAiUpgradeResponse upgrade(String userId, String deviceId, MultipartFile image) {
        UserAccount userAccount = getRequiredUser(userId);
        validateImage(image);

        UUID requestId = UUID.randomUUID();
        GmsImageGenerationClient.GeneratedImage generatedImage = gmsImageGenerationClient.generateEditedImage(
                image,
                buildPrompt(),
                userAccount.userID());

        String resultImageUrl = storeResultImage(requestId, generatedImage);
        return CameraAiUpgradeResponse.ok(requestId.toString(), resultImageUrl);
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private void validateImage(MultipartFile image) {
        if (image == null || image.isEmpty()) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "image 파일이 필요합니다.");
        }
        if (image.getSize() > appCameraAiProperties.maxUploadSizeBytes()) {
            throw new ApiException(ErrorCode.FILE_TOO_LARGE);
        }
        if (!StringUtils.hasText(image.getContentType())
                || !ALLOWED_CONTENT_TYPES.contains(image.getContentType().toLowerCase(Locale.ROOT))) {
            throw new ApiException(ErrorCode.UNSUPPORTED_IMAGE_TYPE);
        }
    }

    private String buildPrompt() {
        return PROMPT;
    }

    private String storeResultImage(UUID requestId, GmsImageGenerationClient.GeneratedImage generatedImage) {
        String outputFormat = normalizeOutputFormat(generatedImage.outputFormat());
        Path resultDirectory = resolveBaseDirectory().resolve(requestId.toString());
        Path resultPath = resultDirectory.resolve("result." + outputFormat);

        try {
            Files.createDirectories(resultDirectory);
            Files.write(resultPath, generatedImage.imageBytes());
        } catch (IOException exception) {
            throw new IllegalStateException("AI 보정 결과 이미지를 저장하지 못했습니다: " + resultPath, exception);
        }

        String relativePath = normalizeRelativePath(resolveResultDirName() + "/" + requestId + "/result." + outputFormat);
        return toStaticUrl(relativePath);
    }

    private Path resolveBaseDirectory() {
        return appHairProperties.staticRootPath().resolve(resolveResultDirName()).normalize();
    }

    private String resolveResultDirName() {
        String configuredValue = StringUtils.hasText(appCameraAiProperties.resultDir())
                ? appCameraAiProperties.resultDir().trim()
                : "camera-ai";
        String normalizedValue = normalizeRelativePath(configuredValue);
        if (!StringUtils.hasText(normalizedValue) || normalizedValue.startsWith("..")) {
            throw new IllegalStateException("camera-ai 결과 저장 디렉터리 설정이 올바르지 않습니다.");
        }
        return normalizedValue;
    }

    private String toStaticUrl(String relativePath) {
        String baseUrl = appHairProperties.staticBaseUrl();
        if (!StringUtils.hasText(baseUrl) || "/".equals(baseUrl.trim())) {
            return "/" + relativePath;
        }
        String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        return normalizedBaseUrl + "/" + relativePath;
    }

    private String normalizeOutputFormat(String outputFormat) {
        if (!StringUtils.hasText(outputFormat)) {
            return "png";
        }
        return outputFormat.trim().toLowerCase(java.util.Locale.ROOT);
    }

    private static String normalizePrompt(String value) {
        return value.replace('\n', ' ').replaceAll("\\s+", " ").trim();
    }

    private String normalizeRelativePath(String value) {
        String normalizedValue = value == null ? "" : value.replace('\\', '/');
        while (normalizedValue.startsWith("/")) {
            normalizedValue = normalizedValue.substring(1);
        }
        return normalizedValue;
    }
}

