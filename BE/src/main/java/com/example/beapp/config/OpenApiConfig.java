package com.example.beapp.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springdoc.core.customizers.OpenApiCustomizer;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.security.SecurityScheme;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI openAPI() {
        return new OpenAPI()
                .components(new Components()
                        .addSecuritySchemes("bearerAuth", new SecurityScheme()
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")))
                .info(new Info()
                        .title("Hairddae API")
                        .version("v1")
                        .description("API 명세서 V1 기반 스켈레톤"));
    }

    @Bean
    public OpenApiCustomizer duplicateTrailingSlashPathCustomizer() {
        return openApi -> {
            Paths sourcePaths = openApi.getPaths();
            if (sourcePaths == null || sourcePaths.isEmpty()) {
                return;
            }

            Paths deduplicatedPaths = new Paths();
            sourcePaths.forEach((path, pathItem) -> addPreferredPath(deduplicatedPaths, sourcePaths, path, pathItem));
            openApi.setPaths(deduplicatedPaths);
        };
    }

    private void addPreferredPath(Paths targetPaths, Paths sourcePaths, String path, PathItem pathItem) {
        String canonicalPath = path.endsWith("/") ? path.substring(0, path.length() - 1) : path;
        String preferredPath = sourcePaths.containsKey(canonicalPath + "/") ? canonicalPath + "/" : path;

        if (!targetPaths.containsKey(preferredPath)) {
            targetPaths.addPathItem(preferredPath, sourcePaths.getOrDefault(preferredPath, pathItem));
        }
    }
}
