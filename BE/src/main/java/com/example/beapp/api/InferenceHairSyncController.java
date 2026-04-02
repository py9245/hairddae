package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.hairs.HairMetadataSyncRequest;
import com.example.beapp.api.dto.hairs.HairMetadataSyncResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppInferenceProperties;
import com.example.beapp.service.HairMetadataSyncService;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

@RestController
@Validated
@RequestMapping("/api/internal/hairs")
public class InferenceHairSyncController {

    private static final String SYNC_HEADER = "X-Inference-Sync-Secret";

    private final HairMetadataSyncService hairMetadataSyncService;
    private final AppInferenceProperties appInferenceProperties;

    public InferenceHairSyncController(
            HairMetadataSyncService hairMetadataSyncService,
            AppInferenceProperties appInferenceProperties) {
        this.hairMetadataSyncService = hairMetadataSyncService;
        this.appInferenceProperties = appInferenceProperties;
    }

    @PostMapping(path = {"/sync", "/sync/"}, consumes = {"multipart/form-data"})
    public ResponseEntity<HairMetadataSyncResponse> sync(
            @RequestHeader(name = SYNC_HEADER, required = false) String syncSecret,
            @RequestParam("dataset_code")
            @NotBlank(message = "dataset_code는 필수입니다.")
            @Pattern(regexp = "^[A-Za-z0-9_-]+$", message = "dataset_code 형식이 올바르지 않습니다.")
            @Size(max = 50, message = "dataset_code는 50자 이하여야 합니다.")
            String datasetCode,
            @RequestParam("name")
            @NotBlank(message = "name은 필수입니다.")
            @Size(max = 120, message = "name은 120자 이하여야 합니다.")
            String name,
            @RequestParam("slug")
            @NotBlank(message = "slug는 필수입니다.")
            @Pattern(regexp = "^[a-z0-9-]+$", message = "slug 형식이 올바르지 않습니다.")
            @Size(max = 120, message = "slug는 120자 이하여야 합니다.")
            String slug,
            @RequestParam("category")
            @NotBlank(message = "category는 필수입니다.")
            @Size(max = 50, message = "category는 50자 이하여야 합니다.")
            String category,
            @RequestParam(value = "description", required = false)
            @Size(max = 5000, message = "description은 5000자 이하여야 합니다.")
            String description,
            @RequestParam(value = "dataset_root_url", required = false)
            @Size(max = 500, message = "dataset_root_url은 500자 이하여야 합니다.")
            String datasetRootUrl,
            @RequestParam(value = "asset_index_url", required = false)
            @Size(max = 500, message = "asset_index_url은 500자 이하여야 합니다.")
            String assetIndexUrl,
            @RequestParam(value = "representative_asset_id", required = false)
            @Size(max = 255, message = "representative_asset_id는 255자 이하여야 합니다.")
            String representativeAssetId,
            @RequestParam(value = "preview_image_url", required = false)
            @Size(max = 500, message = "preview_image_url은 500자 이하여야 합니다.")
            String previewImageUrl,
            @RequestParam(value = "active", required = false) Boolean active,
            @RequestPart(value = "preview_image", required = false) MultipartFile previewImage) {
        validateSyncSecret(syncSecret);
        HairMetadataSyncRequest request = new HairMetadataSyncRequest(
                datasetCode,
                name,
                slug,
                category,
                description,
                datasetRootUrl,
                assetIndexUrl,
                representativeAssetId,
                previewImageUrl,
                active);
        return ResponseEntity.ok(hairMetadataSyncService.upsert(request, previewImage));
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
