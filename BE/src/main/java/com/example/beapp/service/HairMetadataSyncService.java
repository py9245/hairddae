package com.example.beapp.service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Locale;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.hairs.HairMetadataSyncRequest;
import com.example.beapp.api.dto.hairs.HairMetadataSyncResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairEntity;
import com.example.beapp.persistence.repository.HairJpaRepository;

@Service
public class HairMetadataSyncService {

    private static final String PREVIEW_DIRECTORY = "hair-preview";

    private final HairJpaRepository hairJpaRepository;
    private final AppHairProperties appHairProperties;

    public HairMetadataSyncService(HairJpaRepository hairJpaRepository, AppHairProperties appHairProperties) {
        this.hairJpaRepository = hairJpaRepository;
        this.appHairProperties = appHairProperties;
    }

    @Transactional
    public HairMetadataSyncResponse upsert(HairMetadataSyncRequest request, MultipartFile previewImage) {
        String previewImagePath = storePreviewImage(request.datasetCode(), previewImage);
        HairEntity hair = hairJpaRepository.findByDatasetCode(request.datasetCode())
                .or(() -> hairJpaRepository.findBySlug(request.slug()))
                .orElseGet(() -> new HairEntity(
                        request.name(),
                        request.category(),
                        previewImagePath,
                        request.description()));

        boolean created = hair.getId() == null;
        hair.applyCatalogMetadata(
                request.name(),
                request.slug(),
                request.category(),
                request.datasetCode(),
                previewImagePath,
                request.description(),
                request.active() == null || request.active());
        HairEntity saved = hairJpaRepository.save(hair);
        return HairMetadataSyncResponse.ok(saved.getId().intValue(), saved.getDatasetCode(), created);
    }

    private String storePreviewImage(String datasetCode, MultipartFile previewImage) {
        if (previewImage == null || previewImage.isEmpty()) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "preview_image는 필수입니다.");
        }
        String contentType = previewImage.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "preview_image는 이미지 파일이어야 합니다.");
        }

        String extension = resolveExtension(previewImage.getOriginalFilename(), contentType);
        Path targetDirectory = appHairProperties.staticRootPath()
                .resolve(PREVIEW_DIRECTORY)
                .resolve(datasetCode);
        Path targetPath = targetDirectory.resolve("main." + extension);

        try {
            Files.createDirectories(targetDirectory);
            clearPreviousPreviewFiles(targetDirectory, targetPath.getFileName().toString());
            try (InputStream inputStream = previewImage.getInputStream()) {
                Files.copy(inputStream, targetPath, StandardCopyOption.REPLACE_EXISTING);
            }
        } catch (IOException exception) {
            throw new IllegalStateException("대표 헤어 이미지를 저장하지 못했습니다: " + targetPath, exception);
        }

        return normalizeStaticPath(PREVIEW_DIRECTORY + "/" + datasetCode + "/main." + extension);
    }

    private void clearPreviousPreviewFiles(Path targetDirectory, String keepFileName) throws IOException {
        if (!Files.isDirectory(targetDirectory)) {
            return;
        }
        try (var paths = Files.list(targetDirectory)) {
            paths.filter(Files::isRegularFile)
                    .filter(path -> !path.getFileName().toString().equals(keepFileName))
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException exception) {
                            throw new IllegalStateException("이전 대표 헤어 이미지를 정리하지 못했습니다: " + path, exception);
                        }
                    });
        }
    }

    private String resolveExtension(String originalFilename, String contentType) {
        if (originalFilename != null) {
            int dotIndex = originalFilename.lastIndexOf('.');
            if (dotIndex >= 0 && dotIndex < originalFilename.length() - 1) {
                return originalFilename.substring(dotIndex + 1).toLowerCase(Locale.ROOT);
            }
        }
        return switch (contentType.toLowerCase(Locale.ROOT)) {
            case "image/png" -> "png";
            case "image/webp" -> "webp";
            case "image/jpeg", "image/jpg" -> "jpg";
            default -> "bin";
        };
    }

    private String normalizeStaticPath(String relativePath) {
        String baseUrl = appHairProperties.staticBaseUrl();
        if (baseUrl == null || baseUrl.isBlank() || "/".equals(baseUrl)) {
            return "/" + relativePath;
        }
        return (baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl)
                + "/"
                + relativePath;
    }
}
