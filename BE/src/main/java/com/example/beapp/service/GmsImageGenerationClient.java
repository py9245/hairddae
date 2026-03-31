package com.example.beapp.service;

import java.io.IOException;
import java.time.Duration;
import java.util.Base64;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.client.MultipartBodyBuilder;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppCameraAiProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@Service
public class GmsImageGenerationClient {

    private static final Logger log = LoggerFactory.getLogger(GmsImageGenerationClient.class);

    private final RestClient.Builder restClientBuilder;
    private final AppCameraAiProperties appCameraAiProperties;

    public GmsImageGenerationClient(RestClient.Builder restClientBuilder, AppCameraAiProperties appCameraAiProperties) {
        this.restClientBuilder = restClientBuilder;
        this.appCameraAiProperties = appCameraAiProperties;
    }

    public GeneratedImage generateEditedImage(MultipartFile image, String prompt, String userId) {
        validateConfiguration();

        try {
            MultipartBodyBuilder bodyBuilder = new MultipartBodyBuilder();
            bodyBuilder.part("model", appCameraAiProperties.modelName());
            bodyBuilder.part("prompt", prompt);
            bodyBuilder.part("image", new NamedByteArrayResource(image.getBytes(), resolveFilename(image)))
                    .header(HttpHeaders.CONTENT_TYPE, resolveContentType(image));

            GmsImageResponse response = restClient().post()
                    .uri("/images/edits")
                    .headers(headers -> headers.setBearerAuth(appCameraAiProperties.providerAuthToken()))
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(bodyBuilder.build())
                    .retrieve()
                    .body(GmsImageResponse.class);

            if (response == null || response.data() == null || response.data().isEmpty()) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 응답에 이미지 데이터가 없습니다.");
            }

            GmsImageData firstImage = response.data().get(0);
            if (!StringUtils.hasText(firstImage.b64Json())) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 응답에 b64_json 이미지가 없습니다.");
            }

            try {
                byte[] decodedImage = Base64.getDecoder().decode(firstImage.b64Json());
                return new GeneratedImage(decodedImage, resolveOutputFormat(response, firstImage));
            } catch (IllegalArgumentException exception) {
                throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 이미지 응답을 해석하지 못했습니다.");
            }
        } catch (IOException exception) {
            throw new IllegalStateException("업로드 이미지를 읽지 못했습니다.", exception);
        } catch (ResourceAccessException exception) {
            log.error("GMS images/edits timeout: {}", exception.getMessage());
            throw new ApiException(ErrorCode.CAMERA_AI_TIMEOUT, "GMS 요청이 시간 내에 완료되지 않았습니다.");
        } catch (RestClientResponseException exception) {
            log.error(
                    "GMS images/edits failed. status={} body={}",
                    exception.getStatusCode().value(),
                    abbreviate(exception.getResponseBodyAsString(), 1000));
            throw new ApiException(
                    ErrorCode.CAMERA_AI_FAILED,
                    "GMS 호출에 실패했습니다. status=%d".formatted(exception.getStatusCode().value()));
        } catch (RestClientException exception) {
            log.error("GMS images/edits error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.CAMERA_AI_FAILED, "GMS 호출 중 오류가 발생했습니다.");
        }
    }

    private RestClient restClient() {
        Duration timeout = Duration.ofMillis(Math.max(appCameraAiProperties.requestTimeoutMs(), 1L));
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(timeout);
        requestFactory.setReadTimeout(timeout);

        RestClient.Builder builder = restClientBuilder.requestFactory(requestFactory);
        if (StringUtils.hasText(appCameraAiProperties.providerBaseUrl())) {
            builder = builder.baseUrl(appCameraAiProperties.providerBaseUrl().trim());
        }
        return builder.build();
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

    private static final class NamedByteArrayResource extends ByteArrayResource {

        private final String filename;

        private NamedByteArrayResource(byte[] byteArray, String filename) {
            super(byteArray);
            this.filename = filename;
        }

        @Override
        public String getFilename() {
            return filename;
        }
    }
}
