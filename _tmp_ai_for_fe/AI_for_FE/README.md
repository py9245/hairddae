# AI for FE

`/home/yusin/S14P21M101/_tmp_ai_for_fe/AI_for_FE` 는 FE 개발자 인수인계를 위한 별도 패키지입니다.

이 문서는 두 시점을 함께 반영합니다.
- 기존 `BE` 브랜치 시점에 FE가 받아야 했던 초기 handoff 구조
- 지금 모노레포 `FE` 폴더에서 실제로 반영된 구조와 차이

핵심은 다음입니다.
- 현재 권장 렌더 경로는 `프레임마다 추천 API 호출`이 아닙니다.
- `GET /api/hairs/recommend` 로 최초 bootstrap 을 1회 수행합니다.
- 응답의 `datasetRootUrl`, `assetIndexUrl` 를 바탕으로 FE가 `/static/...` 자산을 직접 읽습니다.
- 이후 pose 별 asset 선택은 FE 로컬에서 수행합니다.
- 오버레이는 `requestAnimationFrame + affine transform` 으로 그립니다.
- 현재 BE 웹소켓 `/home/hairapply` 는 렌더 이미지 스트림용이 아니라 `applySessionId` 상태 조회용입니다.

## 현재 실제 구조 요약

### 1. 인증
- 로그인 응답 본문에는 `accessToken` 만 포함됩니다.
- `refreshToken` 은 본문에 포함되지 않고 `Set-Cookie` 로만 내려옵니다.
- FE는 로그인/로그아웃/리프레시 호출 시 `credentials: 'include'` 를 사용해야 합니다.
- 회원가입 프로필 값은 `age` 가 아니라 `birthDate` 입니다.

### 2. 카메라 추천/렌더
- 최초에는 `/api/hairs/recommend?hairId=...` 로 헤어 dataset bootstrap
- 응답 예시
```json
{
  "code": 200,
  "message": "추천 정상",
  "hairID": 1,
  "hairName": "테스트 헤어",
  "datasetCode": "0001",
  "datasetRootUrl": "/static/0001",
  "assetIndexUrl": "/static/0001/manifests/asset_index_v0.json",
  "asset": {
    "assetID": "base_pose_bank__yaw+00_pitch+01_roll-01_frame000922",
    "poseKey": "yaw+00_pitch+01_roll-01",
    "yaw1deg": 0,
    "pitch1deg": 1,
    "roll1deg": -1,
    "anchorsUrl": "/static/0001/anchors/...",
    "metadataUrl": "/static/0001/metadata/...",
    "hairRgbaUrl": "/static/0001/hair_rgba/...",
    "hairRgbaBBox": {
      "x": 80,
      "y": 358,
      "w": 206,
      "h": 191
    },
    "qualityScore": 0.98
  }
}
```
- 이후 FE가 `asset_index_v0.json` 을 읽고 가장 가까운 pose asset 을 로컬 선택
- 필요한 `metadata`, `anchors`, `hair_rgba` 는 FE 캐시
- 프레임 렌더는 FE가 수행

### 3. 웹소켓
- 경로: `/home/hairapply`
- 목적: `hairapplystart` 로 발급받은 `applySessionId` 상태 조회
- 지원 메시지 타입: `ping`, `status`, `subscribe`
- 서버 이벤트 타입: `connected`, `pong`, `status`, `error`
- 렌더 결과 PNG 를 웹소켓으로 밀어주는 구조는 현재 BE에 없습니다.

## 기존 handoff 와 현재 구조 차이

| 구분 | 초기 handoff 관점 | 현재 실제 구조 |
| --- | --- | --- |
| 추천 요청 | pose 변화마다 `/api/hairs/recommend` 호출 | 최초 bootstrap 후 FE 로컬 pose 선택 |
| 정적 자산 사용 | 응답의 `hairRgbaUrl` 만 바로 사용 | `assetIndex -> metadata/anchors/png` 전체 runtime 사용 |
| 웹소켓 | feature/recommendation 확장 가능성 중심 | 현재는 상태 조회용만 실제 지원 |
| 오버레이 | bbox + drawImage 수준 설명 | affine 정렬 + fallback bbox 정렬 |
| 사용자 프로필 | `age` 여지 존재 | `birthDate` 로 통일 |
| 토큰 | refresh token 을 응답 본문에 둘 수 있는 인상 | refresh token 은 HttpOnly cookie 전용 |

## FE 개발자가 바로 봐야 할 파일
- 문서: `CURRENT_FE_HANDOFF.md`
- 추천 계약: `src/contracts/recommend.ts`
- 웹소켓 계약: `src/contracts/websocket.ts`
- 추천 API 샘플: `src/api/recommend.ts`
- 로컬 asset runtime 샘플: `src/runtime/asset-runtime.ts`
- 오버레이 샘플: `src/overlay/canvas.ts`
- 캐시형 추천 훅 샘플: `src/react/use-hair-recommend-flow.ts`
- 예제 JSON:
  - `examples/ws-feature-message.json`
  - `examples/ws-recommendation-message.json`
  - `examples/ws-status-request.json`
  - `examples/ws-status-response.json`

## 권장 적용 순서
1. 로그인/회원가입 DTO를 현재 BE 계약에 맞춘다.
2. 로그인/로그아웃/리프레시 요청에 `credentials: 'include'` 를 적용한다.
3. 카메라 진입 시 `FaceLandmarker` 를 통해 pose 를 계산한다.
4. 선택한 `hairID` 로 bootstrap recommend 1회를 수행한다.
5. `assetIndexUrl` 기준으로 FE에서 nearest asset 을 고른다.
6. 오버레이는 `buildOverlayAffine()` 와 `drawHairOverlayToCanvas()` 로 매 프레임 렌더한다.
7. `POST /api/home/recodehair` 는 실제 5초 이상 시청 시점에만 호출한다.
8. `/home/hairapply` 웹소켓은 상태 조회용으로만 연결한다.

## 설치
```bash
cd /home/yusin/S14P21M101/_tmp_ai_for_fe/AI_for_FE
pnpm install
pnpm typecheck
```

## 런타임 자산 체크
```bash
./scripts/check-runtime-assets.sh /path/to/public
```

필수 자산:
- `models/face_landmarker.task`
- `mediapipe/`

## 주의
- 브라우저는 EC2 파일시스템 절대경로를 직접 읽을 수 없습니다.
- FE는 반드시 `/static/...` 같은 공개 URL 을 사용해야 합니다.
- `/static/*.json` 은 배포 후 갱신될 수 있으므로 캐시 정책을 너무 공격적으로 잡으면 안 됩니다.
