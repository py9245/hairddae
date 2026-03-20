package com.example.beapp.config;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import com.example.beapp.service.HairSeedImportService;

@Component
@Profile("!test")
public class HairSeedImportRunner implements ApplicationRunner {

    private final HairSeedImportService hairSeedImportService;

    public HairSeedImportRunner(HairSeedImportService hairSeedImportService) {
        this.hairSeedImportService = hairSeedImportService;
    }

    @Override
    public void run(ApplicationArguments args) {
        hairSeedImportService.importDefaultDatasetIfPresent();
    }
}
