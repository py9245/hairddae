package com.example.beapp.config;

import java.nio.file.Path;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.hair")
public record AppHairProperties(
        Path staticRootPath,
        String staticBaseUrl
) {
}
