package com.example.beapp.api.dto.home;

import java.time.OffsetDateTime;

import com.example.beapp.persistence.entity.JobStatus;
import com.example.beapp.persistence.entity.JobType;

public record HairApplyStatusResponse(
        int code,
        String message,
        String applySessionId,
        JobType jobType,
        JobStatus status,
        Integer hairID,
        OffsetDateTime completedAt
) {
    public static HairApplyStatusResponse ok(
            String applySessionId,
            JobType jobType,
            JobStatus status,
            Integer hairId,
            OffsetDateTime completedAt) {
        return new HairApplyStatusResponse(200, "조회 정상", applySessionId, jobType, status, hairId, completedAt);
    }
}
