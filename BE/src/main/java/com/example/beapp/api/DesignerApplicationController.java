package com.example.beapp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.example.beapp.api.dto.mypage.DesignerApplicationRequest;
import com.example.beapp.api.dto.mypage.DesignerApplicationResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.service.DesignerApplicationService;

import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/mypage")
@Validated
@SecurityRequirement(name = "bearerAuth")
public class DesignerApplicationController {

    private final DesignerApplicationService designerApplicationService;

    public DesignerApplicationController(DesignerApplicationService designerApplicationService) {
        this.designerApplicationService = designerApplicationService;
    }

    @PostMapping({"/designer", "/designer/"})
    public ResponseEntity<DesignerApplicationResponse> submit(
            Authentication authentication,
            @Valid @RequestBody DesignerApplicationRequest request) {
        if (authentication == null || authentication.getName() == null) {
            throw new ApiException(ErrorCode.UNAUTHORIZED);
        }
        return ResponseEntity.ok(designerApplicationService.submit(authentication.getName(), request));
    }
}
