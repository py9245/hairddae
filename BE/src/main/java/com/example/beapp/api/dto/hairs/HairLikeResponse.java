package com.example.beapp.api.dto.hairs;

public record HairLikeResponse(
        int code,
        String message,
        int hairID,
        boolean liked,
        int likeCount
) {
    public static HairLikeResponse of(int hairID, boolean liked, int likeCount, String message) {
        return new HairLikeResponse(200, message, hairID, liked, likeCount);
    }
}
