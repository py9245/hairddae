package com.example.beapp.model;

import java.time.LocalDate;

public record UserAccount(
        String userID,
        String encodedPassword,
        LocalDate birthDate,
        String gender,
        LoginType loginType,
        String providerSubject,
        short grade
) {
    public UserAccount(String userID, String encodedPassword, LocalDate birthDate, String gender) {
        this(userID, encodedPassword, birthDate, gender, LoginType.LOCAL, null, (short) 0);
    }

    public UserAccount(String userID, String encodedPassword, LocalDate birthDate, String gender, LoginType loginType) {
        this(userID, encodedPassword, birthDate, gender, loginType, null, (short) 0);
    }

    public UserAccount(
            String userID,
            String encodedPassword,
            LocalDate birthDate,
            String gender,
            LoginType loginType,
            String providerSubject) {
        this(userID, encodedPassword, birthDate, gender, loginType, providerSubject, (short) 0);
    }
}
