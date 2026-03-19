package com.example.beapp.api.dto.hairs;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonProperty;

public record HairAssetIndexV2Response(
        int code,
        String message,
        @JsonProperty("hair_id") int hairId,
        @JsonProperty("dataset_code") String datasetCode,
        @JsonProperty("asset_bundle_schema_version") int assetBundleSchemaVersion,
        List<AssetBundleItem> items
) {
    public static HairAssetIndexV2Response ok(
            int hairId,
            String datasetCode,
            int assetBundleSchemaVersion,
            List<AssetBundleItem> items) {
        return new HairAssetIndexV2Response(
                200,
                "에셋 인덱스 조회 정상",
                hairId,
                datasetCode,
                assetBundleSchemaVersion,
                items);
    }

    public record AssetBundleItem(
            @JsonProperty("asset_id") String assetId,
            @JsonProperty("pose_key") String poseKey,
            @JsonProperty("hair_rgba_url") String hairRgbaUrl,
            @JsonProperty("hair_mask_url") String hairMaskUrl,
            @JsonProperty("anchors_url") String anchorsUrl,
            @JsonProperty("metadata_url") String metadataUrl,
            @JsonProperty("hair_bbox") BoundingBox hairBBox,
            String revision
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
