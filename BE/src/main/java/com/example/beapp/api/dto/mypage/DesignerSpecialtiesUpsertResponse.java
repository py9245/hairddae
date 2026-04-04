package com.example.beapp.api.dto.mypage;

public record DesignerSpecialtiesUpsertResponse(
        int code,
        String message,
        boolean success
) {
    public static DesignerSpecialtiesUpsertResponse ok() {
        return new DesignerSpecialtiesUpsertResponse(200, "자신있는 헤어가 저장되었습니다.", true);
    }
}
