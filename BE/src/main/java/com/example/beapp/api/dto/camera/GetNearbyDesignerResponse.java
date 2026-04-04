package com.example.beapp.api.dto.camera;

import java.util.List;

public record GetNearbyDesignerResponse(
        int code,
        String message,
        List<NearbyDesignerItem> designers
) {
    public static GetNearbyDesignerResponse ok(List<NearbyDesignerItem> designers) {
        return new GetNearbyDesignerResponse(200, "조회 정상", designers);
    }

    public record NearbyDesignerItem(
            String userId,
            String salonAddress,
            double distanceKm,
            double latitude,
            double longitude
    ) {
    }
}
