package com.example.beapp.api.dto;

import java.time.Instant;

public record HealthResponse(String service, String status, Instant timestamp) {
}
