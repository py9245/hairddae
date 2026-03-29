package com.example.beapp.api.dto.home;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;

public record HairClickRequest(
        @JsonProperty("hair_id")
        @JsonAlias("hairID")
        @NotNull @Min(1) Integer hairId,
        @JsonProperty("view_sec")
        @Min(0) Integer viewSec
) {
}
