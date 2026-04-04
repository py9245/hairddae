package com.example.beapp.repository;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Repository;

@Repository
@Profile("test")
public class InMemoryHairCategoryLookupRepository implements HairCategoryLookupRepository {

    private final Map<String, HairCategoryInfo> categories = new ConcurrentHashMap<>();

    public InMemoryHairCategoryLookupRepository() {
        save(new HairCategoryInfo("가르마", "가르마"));
        save(new HairCategoryInfo("긴머리", "긴머리"));
        save(new HairCategoryInfo("단발펌", "단발펌"));
        save(new HairCategoryInfo("댄디컷", "댄디컷"));
        save(new HairCategoryInfo("리젠트컷", "리젠트컷"));
        save(new HairCategoryInfo("묶은머리", "묶은머리"));
        save(new HairCategoryInfo("버즈컷", "버즈컷"));
        save(new HairCategoryInfo("히피펌", "히피펌"));
    }

    @Override
    public Optional<HairCategoryInfo> findByCategoryId(String categoryId) {
        if (categoryId == null) {
            return Optional.empty();
        }
        return Optional.ofNullable(categories.get(categoryId.trim()));
    }

    public void save(HairCategoryInfo hairCategoryInfo) {
        categories.put(hairCategoryInfo.categoryId(), hairCategoryInfo);
    }
}
