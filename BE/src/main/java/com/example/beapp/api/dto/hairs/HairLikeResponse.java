package com.example.beapp.api.dto.hairs;

public record HairLikeResponse(
        int code,
        String message,
        int hairID,
        boolean liked,
        int hairBookMarkCount
) {
    public static HairLikeResponse of(int hairID, boolean liked, int hairBookMarkCount, String message) {
        return new HairLikeResponse(200, message, hairID, liked, hairBookMarkCount);
    }
}
