package com.example.beapp.api.dto.hairs;

public record HairRecommendResponse(
        int code,
        String message,
        int hairID,
        String hairName,
        String datasetCode,
        String datasetRootUrl,
        String assetIndexUrl,
        RecommendedAsset asset
) {
    public static HairRecommendResponse ok(
            int hairID,
            String hairName,
            String datasetCode,
            String datasetRootUrl,
            String assetIndexUrl,
            RecommendedAsset asset
    ) {
        return new HairRecommendResponse(200, "추천 정상", hairID, hairName, datasetCode, datasetRootUrl, assetIndexUrl, asset);
    }

    public record RecommendedAsset(
            String assetID,
            String poseKey,
            Integer yaw1deg,
            Integer pitch1deg,
            Integer roll1deg,
            String imageUrl,
            String alphaUrl,
            String anchorsUrl,
            String metadataUrl,
            String hairRgbaUrl,
            BoundingBox hairRgbaBBox,
            Double qualityScore
    ) {
    }

    public record BoundingBox(
            Integer x,
            Integer y,
            Integer w,
            Integer h
    ) {
    }
}
