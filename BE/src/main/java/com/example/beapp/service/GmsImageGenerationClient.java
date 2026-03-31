package com.example.beapp.service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppCameraAiProperties;
import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class GmsImageGenerationClient {

    private static final Logger log = LoggerFactory.getLogger(GmsImageGenerationClient.class);

    private final AppCameraAiProperties appCameraAiProperties;
    private final ObjectMapper objectMapper;

    public GmsImageGenerationClient(AppCameraAiProperties appCameraAiProperties, ObjectMapper objectMapper) {
        this.appCameraAiProperties = appCameraAiProperties;
        this.objectMapper = objectMapper;
    }

    public GeneratedImage generateEditedImage(MultipartFile image, String prompt, String userId) {
        validateConfiguration();

        try {
            String requestBody = objectMapper.writeValueAsString(buildRequest(image, prompt));

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(resolveGenerateContentUrl()))
                    .timeout(resolveTimeout())
                    .header("x-goog-api-key", appCameraAiProperties.providerAuthToken())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                    .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                    .build();

            HttpResponse<String> response = httpClient().send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                log.error(
                        "Gemini generateContent failed. status={} body={}",
                        response.statusCode(),
                        abbreviate(response.body(), 2000));
                throw new ApiException(
                        ErrorCode.CAMERA_AI_FAILED,
                        "GMS 호출에 실패했습니다. status=%d".formatted(response.statusCode()));
            }

            GeminiGenerateContentResponse parsedResponse = objectMapper.readValue(
                    response.body(),
                    GeminiGenerateContentResponse.class);

            GeminiInlineData imageData = extractFirstInlineImage(parsedResponse);
            if (imageData == null || !StringUtils.hasText(imageData.data())) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "Gemini 응답에 이미지 데이터가 없습니다.");
            }

            try {
                byte[] decodedImage = Base64.getDecoder().decode(imageData.data());
                return new GeneratedImage(decodedImage, resolveOutputFormat(imageData.mimeType()));
            } catch (IllegalArgumentException exception) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "Gemini 이미지 응답을 해석하지 못했습니다.");
            }
        } catch (HttpTimeoutException exception) {
            log.error("Gemini generateContent timeout: {}", exception.getMessage());
            throw new ApiException(ErrorCode.CAMERA_AI_TIMEOUT, "GMS 요청이 시간 내에 완료되지 않았습니다.");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.error("Gemini generateContent interrupted: {}", exception.getMessage());
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 호출이 중단되었습니다.");
        } catch (ApiException exception) {
            throw exception;
        } catch (IOException exception) {
            log.error("Gemini generateContent response parse error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "Gemini 응답을 해석하지 못했습니다.");
        } catch (Exception exception) {
            log.error("Gemini generateContent error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 호출 중 오류가 발생했습니다.");
        }
    }

    private HttpClient httpClient() {
        return HttpClient.newBuilder()
                .connectTimeout(resolveTimeout())
                .build();
    }

    private Duration resolveTimeout() {
        return Duration.ofMillis(Math.max(appCameraAiProperties.requestTimeoutMs(), 1L));
    }

    private void validateConfiguration() {
        if (!appCameraAiProperties.enabled()) {
            throw new ApiException(ErrorCode.CAMERA_AI_DISABLED);
        }
        if (!StringUtils.hasText(appCameraAiProperties.providerBaseUrl())
                || !StringUtils.hasText(appCameraAiProperties.providerAuthToken())
                || !StringUtils.hasText(appCameraAiProperties.modelName())) {
            throw new ApiException(ErrorCode.CAMERA_AI_DISABLED, "GMS 호출에 필요한 설정이 누락되었습니다.");
        }
    }

    private String resolveContentType(MultipartFile image) {
        return StringUtils.hasText(image.getContentType()) ? image.getContentType() : MediaType.APPLICATION_OCTET_STREAM_VALUE;
    }

    private String resolveGenerateContentUrl() {
        String baseUrl = appCameraAiProperties.providerBaseUrl().trim();
        String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        return normalizedBaseUrl + "/models/" + appCameraAiProperties.modelName().trim() + ":generateContent";
    }

    private GeminiGenerateContentRequest buildRequest(MultipartFile image, String prompt) throws IOException {
        GeminiPart promptPart = new GeminiPart(prompt, null);
        GeminiPart imagePart = new GeminiPart(
                null,
                new GeminiInlineData(resolveContentType(image), Base64.getEncoder().encodeToString(image.getBytes())));

        return new GeminiGenerateContentRequest(
                List.of(new GeminiContent("user", List.of(promptPart, imagePart))),
                new GeminiGenerationConfig(List.of("TEXT", "IMAGE")));
    }

    private GeminiInlineData extractFirstInlineImage(GeminiGenerateContentResponse response) {
        if (response == null || response.candidates() == null) {
            return null;
        }

        for (GeminiCandidate candidate : response.candidates()) {
            if (candidate == null || candidate.content() == null || candidate.content().parts() == null) {
                continue;
            }
            for (GeminiPart part : candidate.content().parts()) {
                if (part != null && part.inlineData() != null && StringUtils.hasText(part.inlineData().data())) {
                    return part.inlineData();
                }
            }
        }
        return null;
    }

    private String resolveOutputFormat(String mimeType) {
        if (StringUtils.hasText(mimeType) && mimeType.contains("/")) {
            String subtype = mimeType.substring(mimeType.indexOf('/') + 1).trim().toLowerCase();
            return "jpeg".equals(subtype) ? "jpg" : subtype;
        }
        return StringUtils.hasText(appCameraAiProperties.outputFormat())
                ? appCameraAiProperties.outputFormat().trim()
                : "png";
    }

    private String abbreviate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength) + "...";
    }

    public record GeneratedImage(
            byte[] imageBytes,
            String outputFormat
    ) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private record GeminiGenerateContentRequest(
            List<GeminiContent> contents,
            @JsonProperty("generationConfig") GeminiGenerationConfig generationConfig
    ) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private record GeminiContent(
            String role,
            List<GeminiPart> parts
    ) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private record GeminiPart(
            String text,
            @JsonProperty("inline_data") @JsonAlias("inlineData") GeminiInlineData inlineData
    ) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    private record GeminiInlineData(
            @JsonProperty("mime_type") @JsonAlias("mimeType") String mimeType,
            String data
    ) {
    }

    private record GeminiGenerationConfig(
            @JsonProperty("responseModalities") List<String> responseModalities
    ) {
    }

    private record GeminiGenerateContentResponse(
            List<GeminiCandidate> candidates
    ) {
    }

    private record GeminiCandidate(
            GeminiContent content
    ) {
    }
}
