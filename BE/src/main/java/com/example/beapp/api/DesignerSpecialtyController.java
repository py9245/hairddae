package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.mypage.DesignerSpecialtiesRequest;
import com.example.beapp.api.dto.mypage.DesignerSpecialtiesResponse;
import com.example.beapp.api.dto.mypage.DesignerSpecialtiesUpsertResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.service.DesignerSpecialtyService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/mypage")
@Validated
@SecurityRequirement(name = "bearerAuth")
public class DesignerSpecialtyController {

    private final DesignerSpecialtyService designerSpecialtyService;

    public DesignerSpecialtyController(DesignerSpecialtyService designerSpecialtyService) {
        this.designerSpecialtyService = designerSpecialtyService;
    }

    @PostMapping({"/designer/specialties", "/designer/specialties/"})
    public ResponseEntity<DesignerSpecialtiesUpsertResponse> replace(
            Authentication authentication,
            @Valid @RequestBody DesignerSpecialtiesRequest request) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(designerSpecialtyService.replace(authentication.getName(), request));
    }

    @PutMapping({"/designer/specialties", "/designer/specialties/"})
    public ResponseEntity<DesignerSpecialtiesUpsertResponse> update(
            Authentication authentication,
            @Valid @RequestBody DesignerSpecialtiesRequest request) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(designerSpecialtyService.replace(authentication.getName(), request));
    }

    @GetMapping({"/designer/specialties", "/designer/specialties/"})
    public ResponseEntity<DesignerSpecialtiesResponse> get(Authentication authentication) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(designerSpecialtyService.get(authentication.getName()));
    }
}
