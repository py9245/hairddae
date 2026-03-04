package com.example.backend.api;

import java.util.HashMap;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/test")
public class TestController {

    @GetMapping
    public ResponseEntity<Map<String, Object>> getTest() {
        Map<String, Object> payload = new HashMap<>();
        payload.put("status", "success");
        payload.put("message", "ok");
        return ResponseEntity.ok(payload);
    }
}
