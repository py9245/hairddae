package com.example.beapp.websocket;

import java.io.IOException;

import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import com.example.beapp.api.dto.home.HairApplyStatusResponse;
import com.example.beapp.common.exception.ApiException;
import com.example.beapp.common.exception.ErrorCode;
import com.example.beapp.security.JwtTokenService;
import com.example.beapp.service.HomeService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class HairApplyWebSocketHandler extends TextWebSocketHandler {

    private final ObjectMapper objectMapper;
    private final JwtTokenService jwtTokenService;
    private final HomeService homeService;

    public HairApplyWebSocketHandler(
            ObjectMapper objectMapper,
            JwtTokenService jwtTokenService,
            HomeService homeService) {
        this.objectMapper = objectMapper;
        this.jwtTokenService = jwtTokenService;
        this.homeService = homeService;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) throws IOException {
        sendMessage(session, ServerMessage.connected());
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws IOException {
        HairApplyWebSocketRequest request;
        try {
            request = parseRequest(message.getPayload());
        } catch (IOException exception) {
            sendMessage(session, ServerMessage.error(ErrorCode.INVALID_REQUEST, exception.getMessage()));
            return;
        }

        String messageType = StringUtils.hasText(request.type()) ? request.type().trim().toLowerCase() : "status";

        if ("ping".equals(messageType)) {
            sendMessage(session, ServerMessage.pong());
            return;
        }

        if (!"status".equals(messageType) && !"subscribe".equals(messageType)) {
            sendMessage(session, ServerMessage.error(ErrorCode.INVALID_REQUEST, "지원하지 않는 메시지 타입입니다."));
            return;
        }

        if (!StringUtils.hasText(request.accessToken()) || !StringUtils.hasText(request.applySessionId())) {
            sendMessage(session, ServerMessage.error(ErrorCode.INVALID_REQUEST, "accessToken과 applySessionId가 필요합니다."));
            return;
        }

        try {
            String userId = jwtTokenService.validateAccessToken(request.accessToken()).userId();
            HairApplyStatusResponse statusResponse = homeService.getHairApplyStatus(userId, request.applySessionId());
            sendMessage(session, ServerMessage.status(statusResponse));
        } catch (ApiException exception) {
            sendMessage(session, ServerMessage.error(exception.getErrorCode(), exception.getMessage()));
        }
    }

    @Override
    public void handleTransportError(WebSocketSession session, Throwable exception) throws Exception {
        if (session.isOpen()) {
            session.close(CloseStatus.SERVER_ERROR);
        }
    }

    private HairApplyWebSocketRequest parseRequest(String payload) throws IOException {
        try {
            return objectMapper.readValue(payload, HairApplyWebSocketRequest.class);
        } catch (JsonProcessingException exception) {
            throw new IOException("웹소켓 요청 본문이 JSON 형식이 아닙니다.", exception);
        }
    }

    private void sendMessage(WebSocketSession session, ServerMessage message) throws IOException {
        session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
    }

    private record HairApplyWebSocketRequest(
            String type,
            String accessToken,
            String applySessionId
    ) {
    }

    private record ServerMessage(
            String type,
            String message,
            Integer code,
            Object data
    ) {
        private static ServerMessage connected() {
            return new ServerMessage(
                    "connected",
                    "웹소켓 연결이 완료되었습니다.",
                    200,
                    new ConnectionData("/home/hairapply/"));
        }

        private static ServerMessage pong() {
            return new ServerMessage("pong", "pong", 200, null);
        }

        private static ServerMessage status(HairApplyStatusResponse response) {
            return new ServerMessage("status", "작업 상태 조회에 성공했습니다.", 200, response);
        }

        private static ServerMessage error(ErrorCode errorCode, String message) {
            return new ServerMessage("error", message, errorCode.getCode(), null);
        }
    }

    private record ConnectionData(String endpoint) {
    }
}
