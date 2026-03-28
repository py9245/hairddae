package com.example.beapp.model;

public enum LoginType {
    LOCAL((short) 0),
    GOOGLE((short) 1);

    private final short code;

    LoginType(short code) {
        this.code = code;
    }

    public short code() {
        return code;
    }

    public boolean isLocal() {
        return this == LOCAL;
    }

    public static LoginType fromCode(int code) {
        for (LoginType loginType : values()) {
            if (loginType.code == code) {
                return loginType;
            }
        }
        throw new IllegalArgumentException("Unsupported login type code: " + code);
    }
}
