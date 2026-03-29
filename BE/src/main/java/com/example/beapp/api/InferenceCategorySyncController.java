package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.categories.CategoryMetadataSyncRequest;
import com.example.beapp.api.dto.categories.CategoryMetadataSyncResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.service.CategoryMetadataSyncService;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

@RestController
@Validated
@RequestMapping("/api/internal/categories")
public class InferenceCategorySyncController {

    private static final String SYNC_HEADER = "X-Inference-Sync-Secret";

    private final CategoryMetadataSyncService categoryMetadataSyncService;
    private final AppInferenceProperties appInferenceProperties;

    public InferenceCategorySyncController(
            CategoryMetadataSyncService categoryMetadataSyncService,
            AppInferenceProperties appInferenceProperties
    ) {
        this.categoryMetadataSyncService = categoryMetadataSyncService;
        this.appInferenceProperties = appInferenceProperties;
    }

    @PostMapping(path = {"/sync", "/sync/"}, consumes = {"multipart/form-data"})
    public ResponseEntity<CategoryMetadataSyncResponse> sync(
            @RequestHeader(name = SYNC_HEADER, required = false) String syncSecret,
            @RequestParam("category_id")
            @NotBlank(message = "category_id는 필수입니다.")
            @Pattern(regexp = "^[A-Za-z0-9_-]+$", message = "category_id 형식이 올바르지 않습니다.")
            @Size(max = 50, message = "category_id는 50자 이하여야 합니다.")
            String categoryId,
            @RequestParam("category_name")
            @NotBlank(message = "category_name은 필수입니다.")
            @Size(max = 120, message = "category_name은 120자 이하여야 합니다.")
            String categoryName,
            @RequestParam(value = "description", required = false)
            @Size(max = 5000, message = "description은 5000자 이하여야 합니다.")
            String description,
            @RequestParam(value = "preview_image_url", required = false)
            @Size(max = 500, message = "preview_image_url은 500자 이하여야 합니다.")
            String previewImageUrl,
            @RequestParam(value = "display_order", required = false)
            @Min(value = 0, message = "display_order는 0 이상이어야 합니다.")
            Integer displayOrder,
            @RequestParam(value = "active", required = false) Boolean active,
            @RequestPart(value = "preview_image", required = false) MultipartFile previewImage
    ) {
        validateSyncSecret(syncSecret);
        CategoryMetadataSyncRequest request = new CategoryMetadataSyncRequest(
                categoryId,
                categoryName,
                description,
                previewImageUrl,
                displayOrder,
                active);
        return ResponseEntity.ok(categoryMetadataSyncService.upsert(request, previewImage));
    }

    private void validateSyncSecret(String syncSecret) {
        if (!StringUtils.hasText(appInferenceProperties.metadataSyncSecret())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "APP_INFERENCE_METADATA_SYNC_SECRET 설정이 필요합니다.");
        }
        if (!appInferenceProperties.metadataSyncSecret().equals(syncSecret)) {
            throw new ApiException(ErrorCode.UNAUTHORIZED, "추론 서버 동기화 인증에 실패했습니다.");
        }
    }
}
