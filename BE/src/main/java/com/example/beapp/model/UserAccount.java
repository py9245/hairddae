package com.example.beapp.model;

import java.time.LocalDate;

public record UserAccount(
        String userID,
        String encodedPassword,
        LocalDate birthDate,
        String gender,
        LoginType loginType
) {
    public UserAccount(String userID, String encodedPassword, LocalDate birthDate, String gender) {
        this(userID, encodedPassword, birthDate, gender, LoginType.LOCAL);
    }
}
