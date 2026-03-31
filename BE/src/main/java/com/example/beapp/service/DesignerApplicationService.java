package com.example.beapp.service;

import org.springframework.stereotype.Service;

import com.example.beapp.api.dto.mypage.DesignerApplicationRequest;
import com.example.beapp.api.dto.mypage.DesignerApplicationResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.model.DesignerApplication;
import com.example.beapp.model.UserAccount;
import com.example.beapp.repository.DesignerApplicationRepository;
import com.example.beapp.repository.UserAccountRepository;

@Service
public class DesignerApplicationService {

    private final UserAccountRepository userAccountRepository;
    private final DesignerApplicationRepository designerApplicationRepository;
    private final NaverGeocodingClient naverGeocodingClient;

    public DesignerApplicationService(
            UserAccountRepository userAccountRepository,
            DesignerApplicationRepository designerApplicationRepository,
            NaverGeocodingClient naverGeocodingClient) {
        this.userAccountRepository = userAccountRepository;
        this.designerApplicationRepository = designerApplicationRepository;
        this.naverGeocodingClient = naverGeocodingClient;
    }

    public DesignerApplicationResponse submit(String userId, DesignerApplicationRequest request) {
        UserAccount userAccount = getRequiredUser(userId);
        verifyApplicable(userAccount);

        String certificateNumber = request.certificateNumber().trim();
        String salonAddress = request.salonAddress().trim();
        NaverGeocodingClient.GeocodingCoordinates coordinates = naverGeocodingClient.geocodeAddress(salonAddress);

        designerApplicationRepository.save(new DesignerApplication(
                userAccount.userID(),
                certificateNumber,
                salonAddress,
                request.acquisitionDate(),
                coordinates.latitude(),
                coordinates.longitude()));

        userAccountRepository.save(new UserAccount(
                userAccount.userID(),
                userAccount.encodedPassword(),
                userAccount.birthDate(),
                userAccount.gender(),
                userAccount.loginType(),
                userAccount.providerSubject(),
                (short) 1));

        return DesignerApplicationResponse.ok();
    }

    private UserAccount getRequiredUser(String userId) {
        return userAccountRepository.findByUserId(userId)
                .orElseThrow(() -> new ApiException(ErrorCode.USER_NOT_FOUND));
    }

    private void verifyApplicable(UserAccount userAccount) {
        if (userAccount.grade() == 2) {
            throw new ApiException(ErrorCode.DESIGNER_APPLICATION_ALREADY_EXISTS, "이미 디자이너 계정입니다.");
        }
        if (userAccount.grade() == 1 || designerApplicationRepository.existsByUserId(userAccount.userID())) {
            throw new ApiException(ErrorCode.DESIGNER_APPLICATION_ALREADY_EXISTS);
        }
    }
}
