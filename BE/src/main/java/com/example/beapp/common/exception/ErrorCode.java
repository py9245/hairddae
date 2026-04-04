package com.example.beapp.common.exception;

import org.springframework.http.HttpStatus;

public enum ErrorCode {
    INVALID_REQUEST(HttpStatus.BAD_REQUEST, 400, "요청값 검증 실패"),
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, 401, "인증이 필요합니다."),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, 401, "유효하지 않은 토큰입니다."),
    UNSUPPORTED_IMAGE_TYPE(HttpStatus.BAD_REQUEST, 400, "지원하지 않는 이미지 형식입니다."),
    FILE_TOO_LARGE(HttpStatus.PAYLOAD_TOO_LARGE, 413, "업로드 가능한 이미지 크기를 초과했습니다."),
    CAMERA_AI_DISABLED(HttpStatus.SERVICE_UNAVAILABLE, 503, "AI 보정 기능이 비활성화되어 있습니다."),
    CAMERA_AI_TIMEOUT(HttpStatus.GATEWAY_TIMEOUT, 504, "AI 보정 요청이 시간 내에 완료되지 않았습니다."),
    CAMERA_AI_FAILED(HttpStatus.BAD_GATEWAY, 502, "AI 보정 처리에 실패했습니다."),
    GEOCODING_DISABLED(HttpStatus.SERVICE_UNAVAILABLE, 503, "주소 좌표 변환 기능이 비활성화되어 있습니다."),
    GEOCODING_ADDRESS_NOT_FOUND(HttpStatus.BAD_REQUEST, 400, "주소에 해당하는 좌표를 찾을 수 없습니다."),
    GEOCODING_FAILED(HttpStatus.BAD_GATEWAY, 502, "주소 좌표 변환에 실패했습니다."),
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, 404, "사용자를 찾을 수 없습니다."),
    HAIR_NOT_FOUND(HttpStatus.NOT_FOUND, 404, "헤어를 찾을 수 없습니다."),
    JOB_NOT_FOUND(HttpStatus.NOT_FOUND, 404, "작업을 찾을 수 없습니다."),
    DESIGNER_APPLICATION_ALREADY_EXISTS(HttpStatus.CONFLICT, 409, "이미 디자이너 신청을 완료했습니다."),
    DESIGNER_SPECIALTY_FORBIDDEN(HttpStatus.FORBIDDEN, 403, "승인된 디자이너만 자신있는 헤어를 등록할 수 있습니다."),
    DESIGNER_SPECIALTY_INVALID_CATEGORY(HttpStatus.BAD_REQUEST, 400, "존재하지 않는 카테고리가 포함되어 있습니다."),
    CHAT_TARGET_NOT_DESIGNER(HttpStatus.FORBIDDEN, 403, "선택한 사용자는 디자이너가 아닙니다."),
    CHAT_ROOM_NOT_FOUND(HttpStatus.NOT_FOUND, 404, "채팅방을 찾을 수 없습니다."),
    CHAT_ROOM_FORBIDDEN(HttpStatus.FORBIDDEN, 403, "해당 채팅방에 접근할 수 없습니다."),
    DUPLICATE_USER(HttpStatus.CONFLICT, 409, "이미 존재하는 사용자입니다."),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, 401, "아이디 또는 비밀번호가 올바르지 않습니다.");

    private final HttpStatus httpStatus;
    private final int code;
    private final String message;

    ErrorCode(HttpStatus httpStatus, int code, String message) {
        this.httpStatus = httpStatus;
        this.code = code;
        this.message = message;
    }

    public HttpStatus getHttpStatus() {
        return httpStatus;
    }

    public int getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
