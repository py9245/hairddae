package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.camera.CameraAiUpgradeResponse;
import com.example.beapp.api.dto.camera.GetNearbyDesignerRequest;
import com.example.beapp.api.dto.camera.GetNearbyDesignerResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.service.CameraAiUpgradeService;
import com.example.beapp.service.NearbyDesignerService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Size;

@RestController
@Validated
@RequestMapping("/api/camera")
public class CameraController {

    private final CameraAiUpgradeService cameraAiUpgradeService;
    private final NearbyDesignerService nearbyDesignerService;

    public CameraController(CameraAiUpgradeService cameraAiUpgradeService, NearbyDesignerService nearbyDesignerService) {
        this.cameraAiUpgradeService = cameraAiUpgradeService;
        this.nearbyDesignerService = nearbyDesignerService;
    }

    @PostMapping(path = {"/ai-upgrade", "/ai-upgrade/"}, consumes = {"multipart/form-data"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<CameraAiUpgradeResponse> aiUpgrade(
            Authentication authentication,
            @RequestPart("image") MultipartFile image,
            @RequestParam(value = "device_id", required = false)
            @Size(max = 255, message = "device_id는 255자 이하여야 합니다.")
            String deviceId) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(cameraAiUpgradeService.upgrade(authentication.getName(), deviceId, image));
    }

    @PostMapping(path = {"/get-designer", "/get-designer/"})
    @SecurityRequirement(name = "bearerAuth")
    public ResponseEntity<GetNearbyDesignerResponse> getNearbyDesigners(
            Authentication authentication,
            @Valid @RequestBody GetNearbyDesignerRequest request) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(nearbyDesignerService.getNearbyDesigners(authentication.getName(), request));
    }
}
