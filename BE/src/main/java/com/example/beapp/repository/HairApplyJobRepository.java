package com.example.beapp.repository;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Repository;
import org.springframework.util.StringUtils;

import com.example.beapp.persistence.entity.JobEntity;
import com.example.beapp.persistence.entity.JobStatus;
import com.example.beapp.persistence.entity.JobType;
import com.example.beapp.persistence.repository.JobJpaRepository;

@Repository
public class HairApplyJobRepository {

    private final JobJpaRepository jobJpaRepository;
    private final Map<UUID, HairApplyJobSnapshot> jobs = new ConcurrentHashMap<>();

    public HairApplyJobRepository(ObjectProvider<JobJpaRepository> jobJpaRepositoryProvider) {
        this.jobJpaRepository = jobJpaRepositoryProvider.getIfAvailable();
    }

    public HairApplyJobSnapshot createPending(String userId, Integer hairId) {
        if (jobJpaRepository != null) {
            JobEntity jobEntity = new JobEntity(null, JobType.HAIR_APPLY, JobStatus.PENDING);
            jobEntity.setRequestPayload(Map.of(
                    "userID", userId,
                    "hairID", hairId));
            JobEntity savedJob = jobJpaRepository.save(jobEntity);
            return toSnapshot(savedJob);
        }

        UUID jobId = UUID.randomUUID();
        HairApplyJobSnapshot snapshot = new HairApplyJobSnapshot(
                jobId,
                userId,
                hairId,
                JobType.HAIR_APPLY,
                JobStatus.PENDING,
                null);
        jobs.put(jobId, snapshot);
        return snapshot;
    }

    public Optional<HairApplyJobSnapshot> findById(UUID jobId) {
        if (jobJpaRepository != null) {
            return jobJpaRepository.findById(jobId).map(this::toSnapshot);
        }
        return Optional.ofNullable(jobs.get(jobId));
    }

    private HairApplyJobSnapshot toSnapshot(JobEntity jobEntity) {
        Map<String, Object> requestPayload = jobEntity.getRequestPayload();
        Object hairIdValue = requestPayload == null ? null : requestPayload.get("hairID");
        Integer hairId = hairIdValue instanceof Number number
                ? number.intValue()
                : hairIdValue instanceof String value && StringUtils.hasText(value)
                        ? Integer.valueOf(value)
                        : null;
        String userId = requestPayload != null && requestPayload.get("userID") instanceof String value
                ? value
                : null;

        return new HairApplyJobSnapshot(
                jobEntity.getId(),
                userId,
                hairId,
                jobEntity.getJobType(),
                jobEntity.getStatus(),
                jobEntity.getCompletedAt());
    }

    public record HairApplyJobSnapshot(
            UUID id,
            String userId,
            Integer hairId,
            JobType jobType,
            JobStatus status,
            OffsetDateTime completedAt
    ) {
    }
}
