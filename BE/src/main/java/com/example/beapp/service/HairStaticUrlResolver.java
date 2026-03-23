package com.example.beapp.service;

import java.nio.file.Path;

import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairEntity;

@Service
public class HairStaticUrlResolver {

    private final AppHairProperties appHairProperties;

    public HairStaticUrlResolver(AppHairProperties appHairProperties) {
        this.appHairProperties = appHairProperties;
    }

    public String resolvePreviewImageUrl(HairEntity hair) {
        return resolvePreviewImageUrl(hair.getDatasetCode(), hair.getDatasetRootUrl(), hair.getPreviewImageUrl());
    }

    public String resolvePreviewImageUrl(String datasetCode, String datasetRootUrl, String storedPreviewImageUrl) {
        if (!StringUtils.hasText(storedPreviewImageUrl)) {
            return null;
        }

        String trimmedValue = storedPreviewImageUrl.trim();
        if (isExternalUrl(trimmedValue)) {
            return trimmedValue;
        }

        String staticRelativePath = relativizeStaticRootPath(trimmedValue);
        if (StringUtils.hasText(staticRelativePath)) {
            return toStaticUrl(staticRelativePath);
        }

        if (isStaticUrl(trimmedValue)) {
            return normalizeStaticUrl(trimmedValue);
        }

        String relativePath = normalizeRelativePath(trimmedValue);
        if (!StringUtils.hasText(relativePath)) {
            return null;
        }

        if (StringUtils.hasText(datasetCode) && relativePath.startsWith(datasetCode + "/")) {
            return toStaticUrl(relativePath);
        }

        String resolvedDatasetRootUrl = resolveDatasetRootUrl(datasetCode, datasetRootUrl);
        if (StringUtils.hasText(resolvedDatasetRootUrl)) {
            return trimTrailingSlash(resolvedDatasetRootUrl) + "/" + normalizeRelativePath(relativePath);
        }

        if (StringUtils.hasText(datasetCode)) {
            return buildDatasetAssetUrl(datasetCode, relativePath);
        }
        return toStaticUrl(relativePath);
    }

    public String resolveDatasetRootUrl(HairEntity hair) {
        return resolveDatasetRootUrl(hair.getDatasetCode(), hair.getDatasetRootUrl());
    }

    public String resolveDatasetRootUrl(String datasetCode, String storedDatasetRootUrl) {
        if (StringUtils.hasText(storedDatasetRootUrl)) {
            String trimmedValue = storedDatasetRootUrl.trim();
            if (isExternalUrl(trimmedValue)) {
                return trimTrailingSlash(trimmedValue);
            }

            String staticRelativePath = relativizeStaticRootPath(trimmedValue);
            if (StringUtils.hasText(staticRelativePath)) {
                return trimTrailingSlash(toStaticUrl(staticRelativePath));
            }

            if (isStaticUrl(trimmedValue)) {
                return trimTrailingSlash(normalizeStaticUrl(trimmedValue));
            }
        }

        if (!StringUtils.hasText(datasetCode)) {
            return null;
        }
        return trimTrailingSlash(toStaticUrl(datasetCode));
    }

    public String resolveAssetIndexUrl(HairEntity hair) {
        if (StringUtils.hasText(hair.getAssetIndexUrl())) {
            String assetIndexUrl = hair.getAssetIndexUrl().trim();
            if (isExternalUrl(assetIndexUrl)) {
                return assetIndexUrl;
            }

            String staticRelativePath = relativizeStaticRootPath(assetIndexUrl);
            if (StringUtils.hasText(staticRelativePath)) {
                return toStaticUrl(staticRelativePath);
            }

            if (isStaticUrl(assetIndexUrl)) {
                return normalizeStaticUrl(assetIndexUrl);
            }

            String relativePath = normalizeRelativePath(assetIndexUrl);
            if (StringUtils.hasText(hair.getDatasetCode()) && relativePath.startsWith(hair.getDatasetCode() + "/")) {
                return toStaticUrl(relativePath);
            }

            String datasetRootUrl = resolveDatasetRootUrl(hair);
            if (StringUtils.hasText(datasetRootUrl)) {
                return trimTrailingSlash(datasetRootUrl) + "/" + relativePath;
            }
            return assetIndexUrl;
        }

        if (hair.getId() == null) {
            return null;
        }
        return "/api/hairs/%d/asset-index".formatted(hair.getId());
    }

    public String buildDatasetAssetUrl(String datasetCode, String relativePath) {
        if (!StringUtils.hasText(datasetCode) || !StringUtils.hasText(relativePath)) {
            return null;
        }
        return resolveDatasetRootUrl(datasetCode, null) + "/" + normalizeRelativePath(relativePath);
    }

    private String normalizeStaticUrl(String value) {
        String normalizedValue = normalizeRelativePath(value);
        String normalizedBasePath = normalizeRelativePath(normalizedStaticBaseUrl());
        if (StringUtils.hasText(normalizedBasePath)) {
            if (normalizedValue.equals(normalizedBasePath)) {
                return normalizedStaticBaseUrl();
            }
            if (normalizedValue.startsWith(normalizedBasePath + "/")) {
                normalizedValue = normalizedValue.substring(normalizedBasePath.length() + 1);
            }
        }
        return toStaticUrl(normalizedValue);
    }

    private String toStaticUrl(String relativePath) {
        String normalizedRelativePath = normalizeRelativePath(relativePath);
        String staticBaseUrl = normalizedStaticBaseUrl();
        if (!StringUtils.hasText(normalizedRelativePath)) {
            return StringUtils.hasText(staticBaseUrl) ? staticBaseUrl : "/";
        }

        String normalizedBasePath = normalizeRelativePath(staticBaseUrl);
        if (StringUtils.hasText(normalizedBasePath)
                && (normalizedRelativePath.equals(normalizedBasePath)
                || normalizedRelativePath.startsWith(normalizedBasePath + "/"))) {
            return "/" + normalizedRelativePath;
        }
        if (!StringUtils.hasText(staticBaseUrl)) {
            return "/" + normalizedRelativePath;
        }
        return staticBaseUrl + "/" + normalizedRelativePath;
    }

    private String relativizeStaticRootPath(String value) {
        try {
            Path candidatePath = Path.of(value);
            if (!candidatePath.isAbsolute()) {
                return null;
            }
            Path staticRootPath = appHairProperties.staticRootPath().normalize().toAbsolutePath();
            Path normalizedCandidatePath = candidatePath.normalize().toAbsolutePath();
            if (!normalizedCandidatePath.startsWith(staticRootPath)) {
                return null;
            }
            return normalizeRelativePath(staticRootPath.relativize(normalizedCandidatePath).toString().replace('\\', '/'));
        } catch (RuntimeException exception) {
            return null;
        }
    }

    private boolean isStaticUrl(String value) {
        if (!StringUtils.hasText(value) || !value.startsWith("/")) {
            return false;
        }
        String staticBaseUrl = normalizedStaticBaseUrl();
        return !StringUtils.hasText(staticBaseUrl)
                || value.equals(staticBaseUrl)
                || value.startsWith(staticBaseUrl + "/");
    }

    private boolean isExternalUrl(String value) {
        return value.startsWith("http://") || value.startsWith("https://");
    }

    private String normalizedStaticBaseUrl() {
        String value = appHairProperties.staticBaseUrl();
        if (!StringUtils.hasText(value) || "/".equals(value.trim())) {
            return "";
        }
        String trimmedValue = trimTrailingSlash(value.trim());
        return trimmedValue.startsWith("/") ? trimmedValue : "/" + trimmedValue;
    }

    private String trimTrailingSlash(String value) {
        return value != null && value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private String normalizeRelativePath(String value) {
        String normalizedValue = value == null ? "" : value.replace('\\', '/');
        while (normalizedValue.startsWith("/")) {
            normalizedValue = normalizedValue.substring(1);
        }
        return normalizedValue;
    }
}
