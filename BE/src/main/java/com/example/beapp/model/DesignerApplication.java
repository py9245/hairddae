package com.example.beapp.model;

import java.time.LocalDate;

public record DesignerApplication(
        String userId,
        String certificateNumber,
        String salonAddress,
        LocalDate acquisitionDate,
        Double salonLatitude,
        Double salonLongitude
) {
}
