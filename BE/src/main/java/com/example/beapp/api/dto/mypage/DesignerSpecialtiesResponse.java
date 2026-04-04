package com.example.beapp.api.dto.mypage;

import java.util.List;

public record DesignerSpecialtiesResponse(
        int code,
        String message,
        List<DesignerSpecialtyItem> specialties
) {
    public static DesignerSpecialtiesResponse ok(List<DesignerSpecialtyItem> specialties) {
        return new DesignerSpecialtiesResponse(200, "조회 정상", specialties);
    }

    public record DesignerSpecialtyItem(
            String categoryID,
            String categoryName
    ) {
    }
}
