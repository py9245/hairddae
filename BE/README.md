# BE 서비스 개요

- Spring Boot 3.3 + Java 21
- Gradle 기반
- Postgres, Redis, Nginx 리버스 프록시를 포함한 `docker-compose` 템플릿 제공
- 현재 주요 역할은 `JWT 인증`, `RTC bootstrap/resume 응답`, `Inference same-origin 프록시`, `운영/배포 지원`

## 현재 아키텍처

- 브라우저는 항상 `same-origin`의 `/api`, `/ws/inference`, `/rtc/inference` 로만 통신한다.
- `BE`는 `hairapplybootstrap` / `hairapplyresume` 응답으로 `connect_ticket`, `offer_url`, `ice_servers` 를 내려준다.
- 실제 실시간 처리와 미디어 경로는 `FE <-> Inference` 의 `RTC` 세션에서 동작한다.
- `BE` 내부의 legacy WebSocket 상태 조회 경로는 제거되었고, 현재 기준 경로는 `RTC bootstrap` 중심이다.

## 로컬 실행

```
./gradlew bootRun
```

필수 환경변수 예시는 아래 항목을 기준으로 직접 `.env`에 관리한다.

- `SPRING_DATASOURCE_URL`
- `SPRING_DATASOURCE_USERNAME`
- `SPRING_DATASOURCE_PASSWORD`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `APP_SECURITY_JWT_SECRET`
- `APP_SECURITY_JWT_ISSUER`
- `APP_INFERENCE_NODE_ID`
- `APP_INFERENCE_WS_BASE_URL`
- `APP_INFERENCE_RTC_OFFER_URL`
- `APP_INFERENCE_RTC_ICE_SERVERS_JSON`
- `APP_INFERENCE_METADATA_SYNC_SECRET`
- `INFERENCE_UPSTREAM_HOST`
- `INFERENCE_UPSTREAM_PORT`

## Docker 실행

```
docker compose up --build
```

- 외부 노출 포트: 80 (Nginx). 애플리케이션 8080 포트는 컴포즈 네트워크 내부에서만 접근.
- 정적 파일은 `nginx/html`에 배포하면 `/` 경로로 서빙됩니다.

## 기본 엔드포인트

- `GET /api/health` : 헬스 체크 JSON
- `GET /actuator/health` : Spring Actuator 헬스
- `POST /api/home/hairapplybootstrap` : 새 RTC 세션 bootstrap
- `POST /api/home/hairapplyresume` : 기존 apply session 기반 resume
- `POST /api/internal/hairs/sync` : inference 서버가 새 헤어 메타데이터를 업서트하는 내부 API

## 인증

- 로그인 후 `accessToken`, `refreshToken` 쿠키를 사용한다.
- `connect_ticket` 은 `hairapplybootstrap` / `resume` 응답에서만 발급된다.
- `connect_ticket` 은 single-use 이고, RTC offer 시점에 소비된다.
- `POST /api/internal/hairs/sync` 는 `X-Inference-Sync-Secret` 헤더와 `APP_INFERENCE_METADATA_SYNC_SECRET` 일치 여부로 인증한다.

## 헤어 메타데이터 동기화

- `BE`는 더 이상 static asset path를 seed import 하는 주체가 아니다.
- 새 헤어스타일이 inference 서버에 추가되면 inference가 `POST /api/internal/hairs/sync` 로 아래 메타데이터를 보낸다.
- 필수 필드: `dataset_code`, `name`, `slug`, `category`, `preview_image`
- 선택 필드: `description`, `active`
- `dataset_code` 는 `BE`와 `Inference`가 공유하는 안정적인 헤어 식별자다.

예시:

```bash
curl -X POST https://<be-domain>/api/internal/hairs/sync \
  -H "X-Inference-Sync-Secret: <APP_INFERENCE_METADATA_SYNC_SECRET>" \
  -F "dataset_code=0003" \
  -F "name=wolf cut" \
  -F "slug=wolf-cut" \
  -F "category=medium" \
  -F "description=wolf cut metadata" \
  -F "active=true" \
  -F "preview_image=@/path/to/main.png"
```

## 문서

- [`BE/docs/rtc-bootstrap-contract.md`](/home/yusin/S14P21M101/BE/docs/rtc-bootstrap-contract.md): bootstrap/resume 계약, `connect_ticket` 정책, 필수 env
- [`BE/docs/fe-api-setup.md`](/home/yusin/S14P21M101/BE/docs/fe-api-setup.md): FE same-origin 통신 기준 요약
