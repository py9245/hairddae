package com.example.beapp.api.dto.mypage;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record DesignerApplicationRequest(
        @NotBlank(message = "certificateNumber는 필수입니다.")
        @Size(max = 255, message = "certificateNumber는 255자 이하여야 합니다.")
        String certificateNumber,

        @NotBlank(message = "salonAddress는 필수입니다.")
        @Size(max = 500, message = "salonAddress는 500자 이하여야 합니다.")
        String salonAddress
) {
}
