package com.example.beapp.common.api;

import java.time.Instant;
import java.util.List;

public record ApiErrorResponse(
        int code,
        String message,
        List<FieldValidationError> errors,
        String path,
        Instant timestamp
) {
    public static ApiErrorResponse of(int code, String message, List<FieldValidationError> errors, String path) {
        return new ApiErrorResponse(code, message, errors, path, Instant.now());
    }
}
