package com.example.beapp;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.ActiveProfiles;

import com.example.beapp.service.HairMetadataSyncService;

@SpringBootTest
@ActiveProfiles("test")
class BeAppApplicationTests {

	@MockBean
	private HairMetadataSyncService hairMetadataSyncService;

	@Test
	void contextLoads() {
	}

}
