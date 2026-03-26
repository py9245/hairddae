package com.example.beapp.model;

import java.time.LocalDate;

public record UserAccount(
        String userID,
        String encodedPassword,
        LocalDate birthDate,
        String gender,
        LoginType loginType,
        String providerSubject
) {
    public UserAccount(String userID, String encodedPassword, LocalDate birthDate, String gender) {
        this(userID, encodedPassword, birthDate, gender, LoginType.LOCAL, null);
    }

    public UserAccount(String userID, String encodedPassword, LocalDate birthDate, String gender, LoginType loginType) {
        this(userID, encodedPassword, birthDate, gender, loginType, null);
    }
}
