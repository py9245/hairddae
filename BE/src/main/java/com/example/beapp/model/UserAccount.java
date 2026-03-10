package com.example.beapp.model;

public record UserAccount(
        String userID,
        String encodedPassword,
        Integer age,
        String gender
) {
}
