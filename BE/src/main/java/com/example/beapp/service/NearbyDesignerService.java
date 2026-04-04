package com.example.beapp.service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Comparator;
import java.util.List;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import com.example.beapp.api.dto.camera.GetNearbyDesignerRequest;
import com.example.beapp.api.dto.camera.GetNearbyDesignerResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.DesignerApplication;
import com.example.beapp.model.DesignerSpecialty;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerApplicationRepository;
import com.example.beapp.repository.DesignerSpecialtyRepository;
import com.example.beapp.repository.HairLookupRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class NearbyDesignerService {

    private static final double EARTH_RADIUS_KM = 6371.0;

    private final HairLookupRepository hairLookupRepository;
    private final DesignerSpecialtyRepository designerSpecialtyRepository;
    private final DesignerApplicationRepository designerApplicationRepository;
    private final UserAccountRepository userAccountRepository;

    public NearbyDesignerService(
            HairLookupRepository hairLookupRepository,
            DesignerSpecialtyRepository designerSpecialtyRepository,
            DesignerApplicationRepository designerApplicationRepository,
            UserAccountRepository userAccountRepository) {
        this.hairLookupRepository = hairLookupRepository;
        this.designerSpecialtyRepository = designerSpecialtyRepository;
        this.designerApplicationRepository = designerApplicationRepository;
        this.userAccountRepository = userAccountRepository;
    }

    @Transactional(readOnly = true)
    public GetNearbyDesignerResponse getNearbyDesigners(String requesterUserId, GetNearbyDesignerRequest request) {
        HairLookupRepository.HairInfo hair = hairLookupRepository.findActiveById(request.hairId())
                .orElseThrow(() -> new ApiException(ErrorCode.HAIR_NOT_FOUND));

        if (!StringUtils.hasText(hair.categoryId())) {
            throw new ApiException(ErrorCode.INVALID_REQUEST, "헤어 카테고리 정보가 없습니다.");
        }

        List<GetNearbyDesignerResponse.NearbyDesignerItem> designers = designerSpecialtyRepository.findAllByCategoryId(hair.categoryId()).stream()
                .map(DesignerSpecialty::userId)
                .distinct()
                .filter(candidateUserId -> !candidateUserId.equals(requesterUserId))
                .map(this::resolveApprovedDesignerWithCoordinates)
                .flatMap(java.util.Optional::stream)
                .map(application -> toItem(application, request.latitude(), request.longitude()))
                .sorted(Comparator
                        .comparingDouble(GetNearbyDesignerResponse.NearbyDesignerItem::distanceKm)
                        .thenComparing(GetNearbyDesignerResponse.NearbyDesignerItem::userId))
                .toList();

        return GetNearbyDesignerResponse.ok(designers);
    }

    private java.util.Optional<DesignerApplication> resolveApprovedDesignerWithCoordinates(String userId) {
        java.util.Optional<UserAccount> user = userAccountRepository.findByUserId(userId);
        if (user.isEmpty() || user.get().grade() != 2) {
            return java.util.Optional.empty();
        }

        return designerApplicationRepository.findByUserId(userId)
                .filter(application -> application.salonLatitude() != null && application.salonLongitude() != null);
    }

    private GetNearbyDesignerResponse.NearbyDesignerItem toItem(
            DesignerApplication application,
            double userLatitude,
            double userLongitude) {
        double distanceKm = roundDistance(calculateDistanceKm(
                userLatitude,
                userLongitude,
                application.salonLatitude(),
                application.salonLongitude()));

        return new GetNearbyDesignerResponse.NearbyDesignerItem(
                application.userId(),
                application.salonAddress(),
                distanceKm,
                application.salonLatitude(),
                application.salonLongitude());
    }

    private double calculateDistanceKm(double fromLat, double fromLon, double toLat, double toLon) {
        double latDiff = Math.toRadians(toLat - fromLat);
        double lonDiff = Math.toRadians(toLon - fromLon);
        double fromLatRad = Math.toRadians(fromLat);
        double toLatRad = Math.toRadians(toLat);

        double a = Math.pow(Math.sin(latDiff / 2), 2)
                + Math.cos(fromLatRad) * Math.cos(toLatRad) * Math.pow(Math.sin(lonDiff / 2), 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return EARTH_RADIUS_KM * c;
    }

    private double roundDistance(double distanceKm) {
        return BigDecimal.valueOf(distanceKm)
                .setScale(2, RoundingMode.HALF_UP)
                .doubleValue();
    }
}
