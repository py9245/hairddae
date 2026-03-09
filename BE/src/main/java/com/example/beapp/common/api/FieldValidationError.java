package com.example.beapp.common.api;

public record FieldValidationError(
        String field,
        Object rejectedValue,
        String reason
) {
}
