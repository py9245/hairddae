# RTC Bootstrap / Resume 계약 정리

작성일: 2026-03-18

## 목적

현재 `BE`의 핵심 역할은 `RTC 세션 시작에 필요한 인증/계약 정보`를 `FE`에 내려주는 것이다.

이 문서는 아래를 정리한다.

- `hairapplybootstrap` / `hairapplyresume` 요청/응답 계약
- `connect_ticket` 발급 및 replay 정책
- `APP_INFERENCE_*` 환경변수의 의미

## 현재 책임 분리

- `FE`
  - 카메라를 열고 `bootstrap` 또는 `resume` 을 호출한다.
  - `RTC offer` 를 same-origin `/rtc/inference/offer` 로 보낸다.
- `BE`
  - 로그인/JWT 쿠키 인증
  - `connect_ticket` 발급
  - `offer_url`, `ice_servers`, static bootstrap 전달
  - same-origin nginx 프록시
- `Inference`
  - RTC offer 수락
  - ticket 검증
  - landmark / render / 결과 프레임 반환

## 엔드포인트

### 1. 새 세션 시작

- `POST /api/home/hairapplybootstrap`
- alias: `POST /api/home/hairapplystart-v2`

요청 예시:

```json
{
  "hair_id": 1,
  "device_id": "browser-device-id",
  "client_capabilities": {
    "feature_schema_version": 2,
    "transform_version": "affine_v1"
  }
}
```

### 2. 기존 세션 재시작

- `POST /api/home/hairapplyresume`
- alias: `POST /api/home/hairapplyresume-v2`

요청 예시:

```json
{
  "apply_session_id": "uuid",
  "device_id": "browser-device-id"
}
```

## 응답 핵심 필드

응답은 아래 세 블록을 포함한다.

### 1. `inference`

- legacy WS fallback 용 정보
- 현재 기본 transport 가 `rtc` 여도 하위 호환을 위해 유지

주요 필드:

- `ws_url`
- `ws_auth_transport`
- `connect_ticket`
- `expires_at`
- `node_id`
- `processed_timeout_ms`
- `heartbeat_interval_ms`
- `idle_ttl_ms`

### 2. `rtc`

- 현재 주요 경로

주요 필드:

- `enabled`
- `offer_url`
- `connect_ticket`
- `expires_at`
- `ice_servers`

### 3. `static`

- FE preload 용 static bundle 정보

주요 필드:

- `base_url`
- `dataset_code`
- `asset_bundle_schema_version`
- `asset_index_url`
- `preload_asset_ids`

## connect_ticket 정책

### 발급

- `BE`가 `InferenceConnectTicketService` 로 발급한다.
- JWT secret / issuer / inference node id 를 기준으로 서명한다.
- `aud=inference`, `tokenType=INFERENCE_CONNECT`, `single_use=true` 성격의 ticket 이다.

### 소비

- ticket 은 `Inference /rtc/offer` 검증 시점에 소비된다.
- `offer 200` 이후만 소비되는 것이 아니라, 검증 단계에 들어가면 재사용 불가로 보는 것이 맞다.

### replay

- 동일 ticket 으로 두 번째 `offer` 를 보내면 `401` 이 날 수 있다.
- 이것은 로그인 실패가 아니라 `ticket replay` 로 해석해야 한다.

### 재시도

- RTC 연결 실패 후 재시도는 기존 ticket 재사용이 아니라
- `POST /api/home/hairapplyresume` 으로 새 ticket 을 받아 다시 `offer` 해야 한다.

## `APP_INFERENCE_*` 단일 원천

현재 `BE`는 아래 값을 기준으로 bootstrap 응답을 구성한다.

- `APP_INFERENCE_WS_BASE_URL`
- `APP_INFERENCE_RTC_OFFER_URL`
- `APP_INFERENCE_RTC_ICE_SERVERS_JSON`
- `APP_INFERENCE_AUDIENCE`
- `APP_INFERENCE_NODE_ID`
- `APP_INFERENCE_CONNECT_TICKET_EXPIRY_SECONDS`
- `APP_INFERENCE_PROCESSED_TIMEOUT_MS`
- `APP_INFERENCE_HEARTBEAT_INTERVAL_MS`
- `APP_INFERENCE_IDLE_TTL_MS`
- `APP_INFERENCE_FEATURE_SCHEMA_VERSION`
- `APP_INFERENCE_ASSET_BUNDLE_SCHEMA_VERSION`
- `APP_INFERENCE_TRANSFORM_VERSION`

이 값들은 `AppInferenceProperties` 를 통해 읽고, `InferenceSessionBootstrapFactory` 에서 bootstrap 응답용 계약으로 변환한다.

즉:

- 설정 원천: `application.yml` + `.env`
- 응답 조립 원천: `InferenceSessionBootstrapFactory`

## 필수 운영 점검

### BE 서버 `.env`

- `APP_SECURITY_JWT_SECRET`
- `APP_SECURITY_JWT_ISSUER`
- `APP_INFERENCE_NODE_ID`
- `APP_INFERENCE_RTC_OFFER_URL`
- `APP_INFERENCE_RTC_ICE_SERVERS_JSON`
- `INFERENCE_UPSTREAM_HOST`
- `INFERENCE_UPSTREAM_PORT`

### Inference 서버 `.env`

아래 값은 반드시 BE와 일치해야 한다.

- `APP_SECURITY_JWT_SECRET`
- `APP_SECURITY_JWT_ISSUER`
- `INFERENCE_NODE_ID`
- `INFERENCE_RTC_ICE_SERVERS_JSON`

## 정리

- 현재 주요 경로는 `RTC`
- `BE`는 `세션 시작과 인증 계약`이 핵심
- `connect_ticket` 은 single-use
- 재시도는 `resume` 으로 새 ticket 발급
- `APP_INFERENCE_*` 는 bootstrap 응답의 유일한 설정 원천으로 유지
