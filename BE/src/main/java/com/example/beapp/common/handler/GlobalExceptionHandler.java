package com.example.beapp.common.handler;

import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import com.example.beapp.common.api.ApiErrorResponse;
import com.example.beapp.common.api.FieldValidationError;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import jakarta.servlet.http.HttpServletRequest;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ApiErrorResponse> handleApiException(ApiException exception, HttpServletRequest request) {
        ErrorCode errorCode = exception.getErrorCode();
        return ResponseEntity.status(errorCode.getHttpStatus())
                .body(ApiErrorResponse.of(errorCode.getCode(), exception.getMessage(), List.of(), request.getRequestURI()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiErrorResponse> handleMethodArgumentNotValid(
            MethodArgumentNotValidException exception,
            HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        ErrorCode.INVALID_REQUEST.getMessage(),
                        exception.getBindingResult().getFieldErrors().stream().map(this::toFieldValidationError).toList(),
                        request.getRequestURI()));
    }

    @ExceptionHandler(BindException.class)
    public ResponseEntity<ApiErrorResponse> handleBindException(BindException exception, HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        ErrorCode.INVALID_REQUEST.getMessage(),
                        exception.getBindingResult().getFieldErrors().stream().map(this::toFieldValidationError).toList(),
                        request.getRequestURI()));
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    public ResponseEntity<ApiErrorResponse> handleHandlerMethodValidation(
            HandlerMethodValidationException exception,
            HttpServletRequest request) {
        List<FieldValidationError> errors = exception.getAllErrors().stream()
                .map(error -> new FieldValidationError(
                        error.getCodes() != null && error.getCodes().length > 0 ? error.getCodes()[0] : "parameter",
                        null,
                        error.getDefaultMessage()))
                .toList();

        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        ErrorCode.INVALID_REQUEST.getMessage(),
                        errors,
                        request.getRequestURI()));
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    public ResponseEntity<ApiErrorResponse> handleMissingRequestHeader(
            MissingRequestHeaderException exception,
            HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        "%s 헤더가 필요합니다.".formatted(exception.getHeaderName()),
                        List.of(new FieldValidationError(exception.getHeaderName(), null, "필수 헤더 누락")),
                        request.getRequestURI()));
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<ApiErrorResponse> handleMissingRequestParameter(
            MissingServletRequestParameterException exception,
            HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        "%s 파라미터가 필요합니다.".formatted(exception.getParameterName()),
                        List.of(new FieldValidationError(exception.getParameterName(), null, "필수 파라미터 누락")),
                        request.getRequestURI()));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiErrorResponse> handleConstraintViolation(
            ConstraintViolationException exception,
            HttpServletRequest request) {
        return ResponseEntity.badRequest()
                .body(ApiErrorResponse.of(
                        ErrorCode.INVALID_REQUEST.getCode(),
                        ErrorCode.INVALID_REQUEST.getMessage(),
                        exception.getConstraintViolations().stream().map(this::toFieldValidationError).toList(),
                        request.getRequestURI()));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiErrorResponse> handleNoResourceFound(
            NoResourceFoundException exception,
            HttpServletRequest request) {
        return ResponseEntity.status(404)
                .body(ApiErrorResponse.of(404, "요청한 경로를 찾을 수 없습니다.", List.of(), request.getRequestURI()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleUnexpectedException(Exception exception, HttpServletRequest request) {
        return ResponseEntity.internalServerError()
                .body(ApiErrorResponse.of(500, "서버 내부 오류가 발생했습니다.", List.of(), request.getRequestURI()));
    }

    private FieldValidationError toFieldValidationError(FieldError fieldError) {
        return new FieldValidationError(fieldError.getField(), fieldError.getRejectedValue(), fieldError.getDefaultMessage());
    }

    private FieldValidationError toFieldValidationError(ConstraintViolation<?> violation) {
        String path = violation.getPropertyPath() == null ? "parameter" : violation.getPropertyPath().toString();
        int separatorIndex = path.lastIndexOf('.');
        String field = separatorIndex >= 0 ? path.substring(separatorIndex + 1) : path;
        return new FieldValidationError(field, violation.getInvalidValue(), violation.getMessage());
    }
}
