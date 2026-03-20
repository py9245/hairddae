package com.example.beapp.websocket;

import java.io.IOException;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import com.example.beapp.api.dto.hairs.HairRecommendResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.service.HairCatalogService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class HairRecommendWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;
    private final HairCatalogService hairCatalogService;

    public HairRecommendWebSocketHandler(
            ObjectMapper objectMapper,
            ObjectProvider<HairCatalogService> hairCatalogServiceProvider) {
        this.objectMapper = objectMapper;
        this.hairCatalogService = hairCatalogServiceProvider.getIfAvailable();
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws IOException {
        sendMessage(session, ServerMessage.connected());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws IOException {
        HairRecommendWebSocketRequest request;
        try {
            request = parseRequest(message.getPayload());
        } catch (IOException exception) {
            sendMessage(session, ServerMessage.error(null, ErrorCode.INVALID_REQUEST, exception.getMessage()));
            return;
        }

        String messageType = StringUtils.hasText(request.type()) ? request.type().trim().toLowerCase() : "recommend";

        if ("ping".equals(messageType)) {
            sendMessage(session, ServerMessage.pong(request.requestId()));
            return;
        }

        if (!"recommend".equals(messageType)) {
            sendMessage(session, ServerMessage.error(
                    request.requestId(),
                    ErrorCode.INVALID_REQUEST,
                    "지원하지 않는 메시지 타입입니다."));
            return;
        }

        if (request.hairId() == null || request.hairId() <= 0) {
            sendMessage(session, ServerMessage.error(
                    request.requestId(),
                    ErrorCode.INVALID_REQUEST,
                    "hairId는 1 이상의 값이어야 합니다."));
            return;
        }

        if (hairCatalogService == null) {
            sendMessage(session, ServerMessage.error(
                    request.requestId(),
                    ErrorCode.INVALID_REQUEST,
                    "추천 서비스를 사용할 수 없습니다."));
            return;
        }

        try {
            HairRecommendResponse response = hairCatalogService.recommend(
                    request.hairId().longValue(),
                    request.yaw1deg(),
                    request.pitch1deg(),
                    request.roll1deg());
            sendMessage(session, ServerMessage.recommend(request.requestId(), response));
        } catch (ApiException exception) {
            sendMessage(session, ServerMessage.error(
                    request.requestId(),
                    exception.getErrorCode(),
                    exception.getMessage()));
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        if (session.isOpen()) {
            session.close(CloseStatus.SERVER_ERROR);
        }
    }

    private HairRecommendWebSocketRequest parseRequest(String payload) throws IOException {
        try {
            return objectMapper.readValue(payload, HairRecommendWebSocketRequest.class);
        } catch (JsonProcessingException exception) {
            throw new IOException("웹소켓 요청 본문이 JSON 형식이 아닙니다.", exception);
        }
    }

    private void sendMessage(WebSocketSession session, ServerMessage message) throws IOException {
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
    }

    private record HairRecommendWebSocketRequest(
            String type,
            Long requestId,
            Integer hairId,
            Integer yaw1deg,
            Integer pitch1deg,
            Integer roll1deg
    ) {
    }

    private record ServerMessage(
            String type,
            String message,
            Integer code,
            Long requestId,
            Object data
    ) {
        private static ServerMessage connected() {
            return new ServerMessage(
                    "connected",
                    "헤어 추천 웹소켓 연결이 완료되었습니다.",
                    200,
                    null,
                    new ConnectionData("/api/hairs/recommend/ws/"));
        }

        private static ServerMessage pong(Long requestId) {
            return new ServerMessage("pong", "pong", 200, requestId, null);
        }

        private static ServerMessage recommend(Long requestId, HairRecommendResponse response) {
            return new ServerMessage("recommend", "헤어 추천에 성공했습니다.", 200, requestId, response);
        }

        private static ServerMessage error(Long requestId, ErrorCode errorCode, String message) {
            return new ServerMessage("error", message, errorCode.getCode(), requestId, null);
        }
    }

    private record ConnectionData(String endpoint) {
    }
}
