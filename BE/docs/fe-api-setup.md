# FE → BE/Inference 통신 가이드

## 기준 원칙

- 브라우저는 항상 same-origin 경로만 사용한다.
- FE가 직접 raw inference host 로 붙지 않는다.
- FE 기준 주요 경로는 아래 세 가지다.

## 브라우저 기준 경로

- API: `fetch('/api/...')`
- RTC signaling: `fetch('/rtc/inference/offer')`
- Inference WebSocket fallback: `wss://<same-origin>/ws/inference/apply`

## Bootstrap 시작

- FE는 `POST /api/home/hairapplybootstrap`
- 또는 `POST /api/home/hairapplyresume`
- 응답에서 아래 정보를 받는다.
  - `apply_session_id`
  - `inference.connect_ticket`
  - `rtc.offer_url`
  - `rtc.ice_servers`
  - `static.asset_index_url`
  - `static.preload_asset_ids`

## 개발 환경

- Vite 개발 서버는 `/api`, `/ws/inference`, `/rtc/inference` 를 프록시한다.
- FE 코드에는 raw inference IP를 직접 넣지 않는 것을 기본으로 한다.

## 배포 환경

- public domain 은 FE/BE nginx 가 받는다.
- nginx 가 `/rtc/inference/*`, `/ws/inference/*` 를 외부 inference upstream 으로 프록시한다.
- inference 서버는 내부적으로 `http` 여도 무방하다.
- 브라우저는 여전히 `https` / `wss` same-origin 만 본다.

## 주의

- `connect_ticket` 은 single-use 이다.
- 첫 `offer` 요청에서 소비되므로, 재시도 시에는 반드시 `hairapplyresume` 으로 새 ticket 을 받아야 한다.
- `rtc.ice_servers` 가 비어 있으면 외부 inference 와의 peer 연결이 실패할 가능성이 높다.
