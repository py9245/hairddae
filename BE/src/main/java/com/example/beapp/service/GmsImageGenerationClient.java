package com.example.beapp.service;

import java.io.ByteArrayOutputStream;
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
import java.util.UUID;

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
            String boundary = "----BeAppGmsBoundary" + UUID.randomUUID();
            byte[] requestBody;
            try {
                requestBody = buildMultipartBody(boundary, image, prompt);
            } catch (IOException exception) {
                throw new IllegalStateException("업로드 이미지를 읽지 못했습니다.", exception);
            }

            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(resolveImagesEditsUrl()))
                    .timeout(resolveTimeout())
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + appCameraAiProperties.providerAuthToken())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .header(HttpHeaders.CONTENT_TYPE, MediaType.MULTIPART_FORM_DATA_VALUE + "; boundary=" + boundary)
                    .POST(HttpRequest.BodyPublishers.ofByteArray(requestBody))
                    .build();

            HttpResponse<String> response = httpClient().send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                log.error(
                        "GMS images/edits failed. status={} body={}",
                        response.statusCode(),
                        abbreviate(response.body(), 2000));
                throw new ApiException(
                        ErrorCode.CAMERA_AI_FAILED,
                        "GMS 호출에 실패했습니다. status=%d".formatted(response.statusCode()));
            }

            GmsImageResponse parsedResponse = objectMapper.readValue(response.body(), GmsImageResponse.class);

            if (parsedResponse.data() == null || parsedResponse.data().isEmpty()) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 응답에 이미지 데이터가 없습니다.");
            }

            GmsImageData firstImage = parsedResponse.data().get(0);
            if (!StringUtils.hasText(firstImage.b64Json())) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 응답에 b64_json 이미지가 없습니다.");
            }

            try {
                byte[] decodedImage = Base64.getDecoder().decode(firstImage.b64Json());
                return new GeneratedImage(decodedImage, resolveOutputFormat(parsedResponse, firstImage));
            } catch (IllegalArgumentException exception) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 이미지 응답을 해석하지 못했습니다.");
            }
        } catch (HttpTimeoutException exception) {
            log.error("GMS images/edits timeout: {}", exception.getMessage());
            throw new ApiException(ErrorCode.CAMERA_AI_TIMEOUT, "GMS 요청이 시간 내에 완료되지 않았습니다.");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.error("GMS images/edits interrupted: {}", exception.getMessage());
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 호출이 중단되었습니다.");
        } catch (ApiException exception) {
            throw exception;
        } catch (IOException exception) {
            log.error("GMS images/edits response parse error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 응답을 해석하지 못했습니다.");
        } catch (Exception exception) {
            log.error("GMS images/edits error: {}", exception.getMessage(), exception);
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

    private String resolveFilename(MultipartFile image) {
        return StringUtils.hasText(image.getOriginalFilename()) ? image.getOriginalFilename() : "camera-capture.png";
    }

    private String resolveContentType(MultipartFile image) {
        return StringUtils.hasText(image.getContentType()) ? image.getContentType() : MediaType.APPLICATION_OCTET_STREAM_VALUE;
    }

    private String resolveImagesEditsUrl() {
        String baseUrl = appCameraAiProperties.providerBaseUrl().trim();
        return baseUrl.endsWith("/") ? baseUrl + "images/edits" : baseUrl + "/images/edits";
    }

    private byte[] buildMultipartBody(String boundary, MultipartFile image, String prompt) throws IOException {
        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        writeTextPart(outputStream, boundary, "model", appCameraAiProperties.modelName());
        writeTextPart(outputStream, boundary, "prompt", prompt);
        writeBinaryPart(outputStream, boundary, "image", resolveFilename(image), resolveContentType(image), image.getBytes());
        outputStream.write(("--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        return outputStream.toByteArray();
    }

    private void writeTextPart(ByteArrayOutputStream outputStream, String boundary, String name, String value) throws IOException {
        outputStream.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        outputStream.write(("Content-Disposition: form-data; name=\"" + escapeQuoted(name) + "\"\r\n\r\n")
                .getBytes(StandardCharsets.UTF_8));
        outputStream.write(value.getBytes(StandardCharsets.UTF_8));
        outputStream.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    private void writeBinaryPart(
            ByteArrayOutputStream outputStream,
            String boundary,
            String name,
            String filename,
            String contentType,
            byte[] bytes) throws IOException {
        outputStream.write(("--" + boundary + "\r\n").getBytes(StandardCharsets.UTF_8));
        outputStream.write(("Content-Disposition: form-data; name=\"" + escapeQuoted(name)
                + "\"; filename=\"" + escapeQuoted(filename) + "\"\r\n").getBytes(StandardCharsets.UTF_8));
        outputStream.write(("Content-Type: " + contentType + "\r\n\r\n").getBytes(StandardCharsets.UTF_8));
        outputStream.write(bytes);
        outputStream.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }

    private String escapeQuoted(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"");
    }

    private String resolveOutputFormat(GmsImageResponse response, GmsImageData firstImage) {
        if (StringUtils.hasText(firstImage.outputFormat())) {
            return firstImage.outputFormat().trim();
        }
        if (StringUtils.hasText(response.outputFormat())) {
            return response.outputFormat().trim();
        }
        return StringUtils.hasText(appCameraAiProperties.outputFormat()) ? appCameraAiProperties.outputFormat().trim() : "png";
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

    private record GmsImageResponse(
            String model,
            @JsonProperty("output_format") String outputFormat,
            List<GmsImageData> data
    ) {
    }

    private record GmsImageData(
            @JsonProperty("b64_json") String b64Json,
            @JsonProperty("output_format") String outputFormat
    ) {
    }
}
