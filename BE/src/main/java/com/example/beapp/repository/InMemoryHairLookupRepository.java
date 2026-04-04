package com.example.beapp.repository;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

@Repository
@Profile("test")
public class InMemoryHairLookupRepository implements HairLookupRepository {

    private final Map<Long, HairInfo> hairs = new ConcurrentHashMap<>();

    public InMemoryHairLookupRepository() {
        save(new HairInfo(5L, "가르마"));
        save(new HairInfo(6L, "댄디컷"));
        save(new HairInfo(7L, "긴머리"));
        save(new HairInfo(8L, "묶은머리"));
    }

    @Override
    public Optional<HairInfo> findActiveById(Long hairId) {
        return Optional.ofNullable(hairs.get(hairId));
    }

    public void save(HairInfo hairInfo) {
        hairs.put(hairInfo.id(), hairInfo);
    }
}
