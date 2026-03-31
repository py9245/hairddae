package com.example.beapp.api.dto.mypage;

public record DesignerApplicationResponse(
        int code,
        String message,
        boolean success
) {
    public static DesignerApplicationResponse ok() {
        return new DesignerApplicationResponse(200, "디자이너 신청이 완료되었습니다.", true);
    }
}
