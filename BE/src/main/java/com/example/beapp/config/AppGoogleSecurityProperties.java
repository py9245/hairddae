package com.example.beapp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

@ConfigurationProperties(prefix = "app.security.google")
public record AppGoogleSecurityProperties(
        @DefaultValue("")
        String clientId,

        @DefaultValue("https://www.googleapis.com/oauth2/v3/certs")
        String jwkSetUri
) {
}
