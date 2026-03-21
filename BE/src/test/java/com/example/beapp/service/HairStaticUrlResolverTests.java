package com.example.beapp.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.nio.file.Path;

import org.junit.jupiter.api.Test;

import com.example.beapp.config.AppHairProperties;
import com.example.beapp.persistence.entity.HairEntity;

class HairStaticUrlResolverTests {

    @Test
    void resolvesDatasetRelativePreviewPathAgainstDatasetRootUrl() {
        HairStaticUrlResolver resolver = new HairStaticUrlResolver(new AppHairProperties(Path.of("/tmp/static"), "/static"));
        HairEntity hair = new HairEntity("leaf cut", "short", null, "desc");
        hair.applyCatalogMetadata(
                "leaf cut",
                "leaf-cut",
                "short",
                "0001",
                "https://inference.example.com/assets/0001",
                "manifests/asset_index_v0.json",
                "asset-1",
                "hair_rgba/preview.png",
                "desc",
                true);

        assertEquals(
                "https://inference.example.com/assets/0001/hair_rgba/preview.png",
                resolver.resolvePreviewImageUrl(hair));
    }

    @Test
    void keepsExistingStaticPreviewUrl() {
        HairStaticUrlResolver resolver = new HairStaticUrlResolver(new AppHairProperties(Path.of("/tmp/static"), "/static"));
        HairEntity hair = new HairEntity("leaf cut", "short", null, "desc");
        hair.applyCatalogMetadata(
                "leaf cut",
                "leaf-cut",
                "short",
                "0001",
                null,
                null,
                null,
                "/static/0001/hair_rgba/preview.png",
                "desc",
                true);

        assertEquals("/static/0001/hair_rgba/preview.png", resolver.resolvePreviewImageUrl(hair));
    }

    @Test
    void resolvesRelativeAssetIndexUrlAgainstDatasetRootUrl() {
        HairStaticUrlResolver resolver = new HairStaticUrlResolver(new AppHairProperties(Path.of("/tmp/static"), "/static"));
        HairEntity hair = new HairEntity("leaf cut", "short", null, "desc");
        hair.applyCatalogMetadata(
                "leaf cut",
                "leaf-cut",
                "short",
                "0001",
                "https://inference.example.com/assets/0001",
                "manifests/asset_index_v0.json",
                "asset-1",
                "hair_rgba/preview.png",
                "desc",
                true);

        assertEquals(
                "https://inference.example.com/assets/0001/manifests/asset_index_v0.json",
                resolver.resolveAssetIndexUrl(hair));
    }

    @Test
    void resolvesStaticRootFilePathToStaticUrl() {
        HairStaticUrlResolver resolver = new HairStaticUrlResolver(new AppHairProperties(Path.of("/opt/be-static"), "/static"));
        HairEntity hair = new HairEntity("leaf cut", "short", null, "desc");
        hair.applyCatalogMetadata(
                "leaf cut",
                "leaf-cut",
                "short",
                "0001",
                null,
                null,
                null,
                "/opt/be-static/0001/hair_rgba/preview.png",
                "desc",
                true);

        assertEquals("/static/0001/hair_rgba/preview.png", resolver.resolvePreviewImageUrl(hair));
    }
}
