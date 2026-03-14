# Current FE Handoff

이 문서는 `AI_for_FE` 초기 전달본과 현재 모노레포 `FE` 코드의 차이를 FE 개발자가 빠르게 파악하기 위한 요약입니다.

## 기준 파일

현재 실제 구현 기준:
- `/home/yusin/S14P21M101/FE/src/hooks/Camera/useHairRecommendFlow.ts`
- `/home/yusin/S14P21M101/FE/src/lib/Camera/assetRuntime.ts`
- `/home/yusin/S14P21M101/FE/src/lib/Camera/overlay.ts`
- `/home/yusin/S14P21M101/FE/src/components/Camera/FaceLandmarksView.tsx`
- `/home/yusin/S14P21M101/FE/src/lib/auth.ts`

이 handoff 패키지에서 대응되는 샘플:
- `src/react/use-hair-recommend-flow.ts`
- `src/runtime/asset-runtime.ts`
- `src/overlay/canvas.ts`
- `src/contracts/websocket.ts`

## 지금 FE에서 바뀐 핵심

### 1. 추천 요청 전략 변경
- 이전: pose 가 바뀔 때마다 `/api/hairs/recommend` 요청
- 현재: 헤어 선택 시 bootstrap 1회 요청 후 `asset_index_v0.json` 기반으로 FE에서 nearest asset 선택

### 2. 렌더 전략 변경
- 이전: `hairRgbaUrl` 이미지를 bbox 위치에 단순 draw
- 현재: `anchors + live landmarks` 로 affine 계산 후 캔버스 오버레이
- fallback 으로 live face bbox 와 metadata face bbox 를 맞추는 보정 경로도 사용

### 3. 웹소켓 역할 축소
- 이전 handoff 에서는 feature/recommendation 메시지 왕복 가능성을 염두에 둠
- 현재 BE는 `/home/hairapply` 에서 apply job 상태 조회만 수행
- 따라서 카메라 실시간 렌더는 WS 가 아니라 FE 로컬 처리 중심

### 4. 인증/프로필 계약 변경
- `refreshToken` 은 HttpOnly cookie 로만 유지
- `accessToken` 은 응답 본문으로 유지
- FE는 `credentials: 'include'` 사용
- 회원가입/프로필은 `birthDate` 사용

## FE 개발 체크리스트

### 인증
- 로그인: body 에서 `accessToken` 저장
- refresh token 은 JS 저장 금지
- 로그인/로그아웃/refresh 요청에 `credentials: 'include'`
- `birthDate` 입력 형식은 `yyyy-MM-dd`

### 카메라
- 추천 API는 bootstrap 용도로 최소화
- `/static/.../manifests/asset_index_v0.json` 을 읽어 nearest asset 계산
- 현재 pose 주변 asset 을 미리 prefetch
- render loop 는 `requestAnimationFrame`

### 오버레이
- `buildOverlayAffine()` 우선 사용
- 삼점 앵커 계산 실패 시 bbox fallback 허용
- 캐시 miss 시 이전 asset 을 유지하고 다음 프레임에서 자연스럽게 교체

### 웹소켓
- `ping` 은 헬스체크 수준으로만 사용
- `status` / `subscribe` 는 `applySessionId` 상태 조회용
- 렌더 결과 이미지 스트림을 기대하지 말 것

## 추천 구조 예시

1. `GET /api/hairs/recommend?hairId=1`
2. 응답에서 `datasetRootUrl`, `assetIndexUrl` 확보
3. `GET /static/0001/manifests/asset_index_v0.json`
4. 현재 pose 와 가장 가까운 asset 선택
5. 필요 asset 에 대해
   - `GET /static/0001/metadata/...json`
   - `GET /static/0001/anchors/...json`
   - `GET /static/0001/hair_rgba/...png`
6. 프레임마다 `buildOverlayAffine()` + `drawHairOverlayToCanvas()`

## 권장 분리

- REST
  - bootstrap recommend
  - 인증
  - recodehair
- WebSocket
  - apply job status
- Static
  - manifest
  - metadata
  - anchors
  - hair RGBA
