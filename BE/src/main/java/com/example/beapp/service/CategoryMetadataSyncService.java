package com.example.beapp.service;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Locale;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import com.example.beapp.api.dto.categories.CategoryMetadataSyncRequest;
import com.example.beapp.api.dto.categories.CategoryMetadataSyncResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairCategoryEntity;
import com.example.beapp.persistence.repository.HairCategoryJpaRepository;

@Service
public class CategoryMetadataSyncService {

    private static final String PREVIEW_DIRECTORY = "category-preview";

    private final HairCategoryJpaRepository hairCategoryJpaRepository;
    private final AppHairProperties appHairProperties;

    public CategoryMetadataSyncService(
            HairCategoryJpaRepository hairCategoryJpaRepository,
            AppHairProperties appHairProperties
    ) {
        this.hairCategoryJpaRepository = hairCategoryJpaRepository;
        this.appHairProperties = appHairProperties;
    }

    @Transactional
    public CategoryMetadataSyncResponse upsert(CategoryMetadataSyncRequest request, MultipartFile previewImage) {
        String categoryId = normalizeCategoryId(request.categoryId());
        if (!StringUtils.hasText(categoryId) || "all".equalsIgnoreCase(categoryId)) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "category_id는 all 이외의 값이어야 합니다.");
        }

        HairCategoryEntity category = hairCategoryJpaRepository.findByCategoryIdIgnoreCase(categoryId)
                .orElseGet(() -> new HairCategoryEntity(
                        categoryId,
                        request.categoryName().trim(),
                        null,
                        request.description()));

        String previewImagePath = resolvePreviewImagePath(category, categoryId, request, previewImage);
        boolean created = category.getId() == null;
        category.applyMetadata(
                categoryId,
                request.categoryName().trim(),
                previewImagePath,
                firstText(request.description(), category.getDescription()),
                request.displayOrder() == null ? safeDisplayOrder(category.getDisplayOrder()) : request.displayOrder(),
                request.active() == null || request.active());
        HairCategoryEntity saved = hairCategoryJpaRepository.save(category);
        return CategoryMetadataSyncResponse.ok(saved.getCategoryId(), created);
    }

    private String resolvePreviewImagePath(
            HairCategoryEntity category,
            String categoryId,
            CategoryMetadataSyncRequest request,
            MultipartFile previewImage
    ) {
        if (previewImage != null && !previewImage.isEmpty()) {
            return storePreviewImage(categoryId, previewImage);
        }
        if (StringUtils.hasText(request.previewImageUrl())) {
            return request.previewImageUrl().trim();
        }
        if (StringUtils.hasText(category.getPreviewImageUrl())) {
            return category.getPreviewImageUrl();
        }
        throw new ApiException(ErrorCode.INVALID_REQUEST, "preview_image 또는 preview_image_url 중 하나는 필수입니다.");
    }

    private String storePreviewImage(String categoryId, MultipartFile previewImage) {
        String contentType = previewImage.getContentType();
        if (contentType == null || !contentType.startsWith("image/")) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "preview_image는 이미지 파일이어야 합니다.");
        }

        String extension = resolveExtension(previewImage.getOriginalFilename(), contentType);
        Path targetDirectory = appHairProperties.staticRootPath()
                .resolve(PREVIEW_DIRECTORY)
                .resolve(categoryId);
        Path targetPath = targetDirectory.resolve("main." + extension);

        try {
            Files.createDirectories(targetDirectory);
            clearPreviousPreviewFiles(targetDirectory, targetPath.getFileName().toString());
            try (InputStream inputStream = previewImage.getInputStream()) {
                Files.copy(inputStream, targetPath, StandardCopyOption.REPLACE_EXISTING);
            }
        } catch (IOException exception) {
            throw new IllegalStateException("대표 카테고리 이미지를 저장하지 못했습니다: " + targetPath, exception);
        }

        return normalizeStaticPath(PREVIEW_DIRECTORY + "/" + categoryId + "/main." + extension);
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
                            throw new IllegalStateException("이전 대표 카테고리 이미지를 정리하지 못했습니다: " + path, exception);
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

    private String normalizeCategoryId(String categoryId) {
        return categoryId == null ? null : categoryId.trim().toLowerCase(Locale.ROOT);
    }

    private int safeDisplayOrder(Integer displayOrder) {
        return displayOrder == null ? 0 : displayOrder;
    }

    private String firstText(String primary, String fallback) {
        return StringUtils.hasText(primary) ? primary.trim() : fallback;
    }
}
