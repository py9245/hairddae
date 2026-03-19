package com.example.beapp.model;

import java.time.LocalDate;

public record UserAccount(
        String userID,
        String encodedPassword,
        LocalDate birthDate,
        String gender
) {
}
