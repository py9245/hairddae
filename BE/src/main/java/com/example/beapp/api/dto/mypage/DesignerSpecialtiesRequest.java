package com.example.beapp.api.dto.mypage;

import java.util.List;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;

public record DesignerSpecialtiesRequest(
        @NotEmpty(message = "categoryIds는 최소 1개 이상이어야 합니다.")
        List<
                @NotBlank(message = "categoryIds에는 빈 값이 들어갈 수 없습니다.")
                @Size(max = 50, message = "categoryId는 50자 이하여야 합니다.")
                String> categoryIds
) {
}
