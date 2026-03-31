package com.example.beapp.service;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.util.UriComponentsBuilder;

import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppNaverGeocodingProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class NaverGeocodingClient {

    private static final Logger log = LoggerFactory.getLogger(NaverGeocodingClient.class);

    private final AppNaverGeocodingProperties appNaverGeocodingProperties;
    private final ObjectMapper objectMapper;

    public NaverGeocodingClient(AppNaverGeocodingProperties appNaverGeocodingProperties, ObjectMapper objectMapper) {
        this.appNaverGeocodingProperties = appNaverGeocodingProperties;
        this.objectMapper = objectMapper;
    }

    public GeocodingCoordinates geocodeAddress(String address) {
        validateConfiguration();

        try {
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(buildUri(address))
                    .timeout(resolveTimeout())
                    .header("X-NCP-APIGW-API-KEY-ID", appNaverGeocodingProperties.apiKeyId().trim())
                    .header("X-NCP-APIGW-API-KEY", appNaverGeocodingProperties.apiKey().trim())
                    .header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                    .GET()
                    .build();

            HttpResponse<String> response = httpClient().send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));

            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                log.error(
                        "Naver geocoding failed. status={} body={}",
                        response.statusCode(),
                        abbreviate(response.body(), 1000));
                throw new ApiException(
                        ErrorCode.GEOCODING_FAILED,
                        "네이버 주소 좌표 변환 호출에 실패했습니다. status=%d".formatted(response.statusCode()));
            }

            NaverGeocodeResponse parsedResponse = objectMapper.readValue(response.body(), NaverGeocodeResponse.class);
            if (parsedResponse.addresses() == null || parsedResponse.addresses().isEmpty()) {
                throw new ApiException(ErrorCode.GEOCODING_ADDRESS_NOT_FOUND, "입력한 미용실 주소를 찾지 못했습니다.");
            }

            NaverAddress first = parsedResponse.addresses().get(0);
            if (!StringUtils.hasText(first.x()) || !StringUtils.hasText(first.y())) {
                throw new ApiException(ErrorCode.GEOCODING_ADDRESS_NOT_FOUND, "주소 좌표 정보가 비어 있습니다.");
            }

            return new GeocodingCoordinates(
                    Double.parseDouble(first.y()),
                    Double.parseDouble(first.x()));
        } catch (HttpTimeoutException exception) {
            log.error("Naver geocoding timeout: {}", exception.getMessage());
            throw new ApiException(ErrorCode.GEOCODING_FAILED, "네이버 주소 좌표 변환 요청이 시간 내에 완료되지 않았습니다.");
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            log.error("Naver geocoding interrupted: {}", exception.getMessage());
            throw new ApiException(ErrorCode.GEOCODING_FAILED, "네이버 주소 좌표 변환 호출이 중단되었습니다.");
        } catch (ApiException exception) {
            throw exception;
        } catch (NumberFormatException | IOException exception) {
            log.error("Naver geocoding parse error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.GEOCODING_FAILED, "네이버 주소 좌표 변환 응답을 해석하지 못했습니다.");
        } catch (Exception exception) {
            log.error("Naver geocoding error: {}", exception.getMessage(), exception);
            throw new ApiException(ErrorCode.GEOCODING_FAILED, "네이버 주소 좌표 변환 중 오류가 발생했습니다.");
        }
    }

    private void validateConfiguration() {
        if (!appNaverGeocodingProperties.enabled()) {
            throw new ApiException(ErrorCode.GEOCODING_DISABLED);
        }
        if (!StringUtils.hasText(appNaverGeocodingProperties.baseUrl())
                || !StringUtils.hasText(appNaverGeocodingProperties.apiKeyId())
                || !StringUtils.hasText(appNaverGeocodingProperties.apiKey())) {
            throw new ApiException(ErrorCode.GEOCODING_DISABLED, "네이버 주소 좌표 변환 설정이 누락되었습니다.");
        }
    }

    private URI buildUri(String address) {
        String baseUrl = appNaverGeocodingProperties.baseUrl().trim();
        String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        return UriComponentsBuilder.fromHttpUrl(normalizedBaseUrl)
                .path("/map-geocode/v2/geocode")
                .queryParam("query", address)
                .build()
                .encode(StandardCharsets.UTF_8)
                .toUri();
    }

    private HttpClient httpClient() {
        return HttpClient.newBuilder()
                .connectTimeout(resolveTimeout())
                .build();
    }

    private Duration resolveTimeout() {
        return Duration.ofMillis(Math.max(appNaverGeocodingProperties.requestTimeoutMs(), 1L));
    }

    private String abbreviate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength) + "...";
    }

    public record GeocodingCoordinates(
            double latitude,
            double longitude
    ) {
    }

    private record NaverGeocodeResponse(
            String status,
            List<NaverAddress> addresses
    ) {
    }

    private record NaverAddress(
            @JsonProperty("x") String x,
            @JsonProperty("y") String y
    ) {
    }
}
