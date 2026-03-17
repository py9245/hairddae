# Real-Time Hair Apply Inference Architecture

## 1. 목표

이 문서는 `/home/yusin/hairddae`의 품질을 유지하면서, 실서비스 환경에서 확장 가능한 헤어 오버레이 아키텍처를 정의한다.

핵심 목표는 다음과 같다.

- `hairddae` 수준의 asset 선택 품질 유지
- 브라우저 카메라 프레임 전체 전송 제거
- `FE <-> Inference` 간 `compact feature` 기반 실시간 통신
- 현재는 `FE/BE/Inference` 동일 서버 배포, 추후 `Inference`만 별도 GPU 서버로 분리 가능
- 여러 사용자가 동시에 접속해도 `steady-state` 기준 `15 FPS`, 즉 `66 ms/frame` 이내의 시각적 반응성 유지
- 구현 직전에 바로 사용할 수 있는 수준의 프로토콜, 상태, 운영 경계를 명시

## 2. 설계의 근거가 되는 POC 사실

이 문서의 계약은 추정이 아니라 `hairddae` POC 구현에서 확인한 사실을 기준으로 한다.

### 2.1 좌표계와 anchor 집합

`hairddae/static/tools/tools/face_feature_utils.py`의 `build_anchor_points()`는 anchor를 모두 `pixel-space`로 생성한다.

- 원점: `top-left`
- 단위: `capture frame pixel`
- bbox: 같은 프레임 픽셀 기준으로 계산
- 필수 anchor:
  - `forehead_center`
  - `left_temple`, `right_temple`
  - `crown`
  - `left_ear_root`, `right_ear_root`
  - `left_side`, `right_side`
  - `lower_left`, `lower_right`
  - `neck_left`, `neck_right`

근거:

- `/home/yusin/hairddae/static/tools/tools/face_feature_utils.py`
- `point_to_pixel()`
- `bbox_from_landmarks()`
- `build_anchor_points()`

### 2.2 retrieval geometry

`hairddae/static/tools/tools/run_hair_overlay_poc.py`의 `derive_geom_from_feature()`는 geometry를 `face_bbox` 기준으로 정규화한다.

- `temple_span_norm = dist(left_temple, right_temple) / face_bbox.w`
- `lower_span_norm = dist(lower_left, lower_right) / face_bbox.w`
- `crown_offset_norm = abs(forehead_center.y - crown.y) / face_bbox.h`
- `face_ratio = (face_bbox.w * face_bbox.h) / (image_width * image_height)`

근거:

- `/home/yusin/hairddae/static/tools/tools/run_hair_overlay_poc.py`
- `derive_geom_from_feature()`
- `retrieval_score()`

### 2.3 affine transform과 blend 절차

`hairddae/static/tools/tools/run_hair_overlay_poc.py`의 overlay 품질은 단순 PNG 덮기가 아니라 버전이 있는 절차로 구성되어 있다.

- 4-point partial affine:
  - `left_temple`
  - `right_temple`
  - `forehead_center`
  - `crown`
- 실패 시 3-point affine fallback
- `hair_bbox` 기반 ROI crop
- warp 후 alpha/mask blur
- ROI blend

근거:

- `/home/yusin/hairddae/static/tools/tools/run_hair_overlay_poc.py`
- `estimate_transform()`
- `compose_overlay_frame()`

### 2.4 로컬 POC 30 FPS 숫자의 의미

로컬 POC에서 30 FPS가 가능했던 사실은 유효하지만, 이 숫자는 실서비스 다중 사용자 처리량의 증거가 아니다.

이유:

- 브라우저 데모는 `inflight` 1개만 허용한다.
- 이전 요청이 끝나기 전에는 다음 프레임을 보내지 않는다.
- 서버 런타임은 landmarker와 overlay를 하나의 lock 안에서 직렬 처리한다.

근거:

- `/home/yusin/hairddae/static/runtime_demo/frontend/app.js`
- `/home/yusin/hairddae/static/runtime_demo/app/runtime_engine.py`

따라서 POC 30 FPS는 다음을 의미한다.

- 단일 사용자
- 로컬 네트워크
- 단일 직렬 파이프라인
- asset 및 모델이 이미 로드된 상태

즉, 실서비스에서 여러 사용자를 상정한 `66 ms` 보장은 별도의 아키텍처 규칙이 필요하다.

## 3. 비목표와 하드 제약

이 문서는 다음을 목표로 하지 않는다.

- 서버가 최종 합성 비디오 프레임을 매 프레임 생성하는 구조
- 공용 인터넷에서 `camera -> remote inference -> asset fetch -> draw` 전체가 모든 사용자에게 항상 `66 ms` 안에 끝난다는 보장
- 프레임 업로드 기반의 `hairddae` POC를 그대로 서비스화하는 것

실서비스에서 하드하게 지켜야 하는 제약은 다음이다.

- 렌더링의 크리티컬 패스는 FE 로컬이어야 한다.
- 네트워크와 asset fetch는 렌더링의 필수 대기 경로가 아니어야 한다.
- WebSocket 버퍼가 무한히 쌓이지 않아야 한다.
- FE와 Inference가 동일한 좌표계와 transform 버전을 사용해야 한다.

## 4. 최종 아키텍처

### 4.1 역할 분리

#### FE

- 브라우저 카메라 획득
- MediaPipe face tracking 실행
- canonical compact feature 생성
- Inference WebSocket 연결
- asset 선택 결과 수신
- 정적 asset preload/cache
- anchor 기반 affine 정렬
- 최종 overlay canvas 렌더링

#### BE (Spring Boot)

- JWT 인증
- `hairapplystart-v2` 시작점 제공
- apply session 생성 및 종료
- inference 접속용 short-lived connect ticket 발급
- 사용 이력, 권한, 세션 상태 관리
- inference 노드 선택 및 라우팅 정보 반환
- reconnect 시 resume ticket 발급

#### Inference (Python ASGI)

- feature 전용 WebSocket endpoint 제공
- `hairddae`식 retrieval score 계산
- session 단위 hysteresis/state 유지
- bounded backpressure 적용
- 최적 asset 선택 결과만 반환

#### Static/Nginx

- dataset static file 서빙
- `hair_rgba`, `anchors`, `metadata`, `manifest` 제공
- 현재는 same-server, 추후 CDN 또는 object storage 연계 가능

### 4.2 중요한 결론

최종 overlay는 `Inference`가 아니라 `FE`가 수행한다.

이 결정이 필요한 이유는 다음과 같다.

- `15 FPS`를 보장하려면 렌더링이 네트워크 응답을 기다리지 않아야 한다.
- asset 선택은 네트워크 의존이어도 괜찮지만, 프레임 draw는 로컬이어야 한다.
- 동일 asset으로도 FE는 매 animation frame마다 계속 부드럽게 렌더할 수 있다.

즉:

- `asset selection loop`는 네트워크 기반
- `render loop`는 브라우저 로컬 기반

## 5. 성능 목표와 SLO

### 5.1 지표 정의

이 문서에서 `15 FPS = 66 ms`는 아래 지표에 대해 사용한다.

- `steady_state_render_latency`
  - 사용자가 머리를 움직인 뒤, 현재 메모리에 있는 asset으로 overlay가 다시 그려질 때까지의 시간
- `warm_asset_switch_latency`
  - feature가 전송된 뒤, 이미 preload된 새 asset 선택 결과가 화면에 반영될 때까지의 시간
- `bootstrap_latency`
  - 카메라 페이지 진입 후 첫 overlay가 보이기까지의 시간

`bootstrap_latency`는 FPS 지표가 아니다. 초기 진입 지연이며, `steady-state 15 FPS`와 구분해서 관리한다.

### 5.2 서비스 SLO

#### 반드시 보장해야 하는 SLO

- `steady_state_render_latency`: same-server 및 remote-inference 모두 `p95 <= 66 ms`
- `render loop fps`: `p95 >= 15 FPS`

#### same-server warm path 목표

다음 조건을 모두 만족할 때만 `selection`까지 포함한 `66 ms` 목표를 잡는다.

- inference가 same-server 또는 매우 낮은 RTT 구간에 존재
- 선택된 asset이 이미 preload/cache 되어 있음
- 세션 backlog가 없음

이 경로의 목표:

- `warm_asset_switch_latency`: `p95 <= 66 ms`

#### cold path 규칙

아래 경로는 `66 ms` 보장 대상이 아니다.

- 첫 진입 시 cold preload
- 미리 받지 않은 asset으로의 첫 전환
- remote inference에서 일시적 RTT 증가
- overload로 인한 throttle 상태

이 경우의 동작 규칙:

- FE는 마지막 확정 asset으로 계속 `15 FPS` 렌더링한다.
- 새 asset 선택과 다운로드는 비동기로 완료된다.
- UI는 끊기지 않고, selection update만 늦어진다.

### 5.3 성능 예산

same-server warm path 기준 권장 예산:

- FE face tracking: `18~28 ms`
- feature packing/serialization: `<= 1 ms`
- FE -> Inference WSS 왕복: `2~8 ms`
- inference scoring/hysteresis: `1~3 ms`
- FE affine draw + blend: `4~10 ms`
- 스케줄링 및 여유 버퍼: `10~15 ms`

합산 목표:

- `p95 <= 66 ms`

### 5.4 여러 사용자를 위한 운영 해석

여러 사용자가 동시에 접속하는 상황에서 `66 ms`를 유지하려면 아래 전제가 필요하다.

- Inference는 feature만 처리하고 MediaPipe를 다시 돌리지 않는다.
- 세션별 큐 깊이는 최대 1이어야 한다.
- asset fetch는 렌더링 경로에 들어오지 않는다.
- same-server MVP라도 전역 직렬 lock 구조를 유지하지 않는다.

즉, POC의 `30 FPS`는 참고 수치일 뿐이며, 서비스에서는 `queue depth`, `event loop lag`, `warm switch p95`가 진짜 기준이다.

## 6. Canonical Feature Contract

### 6.1 버전 고정

새 실시간 경로는 아래 버전으로 고정한다.

- `feature_schema_version = 2`
- `coordinate_space = pixel_v1`
- `anchor_set = face_anchor_v1`
- `transform_version = affine_v1`

버전이 달라지면 FE와 Inference는 서로 호환된다고 가정하지 않는다.

### 6.2 좌표계 규칙

모든 좌표는 `hairddae` POC와 동일한 `pixel-space`를 사용한다.

- 원점: `top-left`
- x 증가 방향: 오른쪽
- y 증가 방향: 아래쪽
- 단위: 현재 capture frame pixel
- `image_size.width`, `image_size.height`는 필수
- `face_bbox`는 같은 pixel-space에서 계산한 정수 값
- `anchors.*.x`, `anchors.*.y`는 같은 pixel-space의 실수 값

### 6.3 필수 anchor 집합

`face_anchor_v1`의 필수 anchor는 다음과 같다.

- `forehead_center`
- `left_temple`, `right_temple`
- `crown`
- `left_ear_root`, `right_ear_root`
- `left_side`, `right_side`
- `lower_left`, `lower_right`
- `neck_left`, `neck_right`

각 anchor는 아래 형태를 따른다.

```json
{ "x": 176.432, "y": 284.117, "confidence": 1.0 }
```

### 6.4 파생 geometry 규칙

Inference는 raw anchor와 bbox를 받아 아래 geometry를 canonical하게 다시 계산한다.

- `temple_span_norm = dist(left_temple, right_temple) / max(1, face_bbox.w)`
- `lower_span_norm = dist(lower_left, lower_right) / max(1, face_bbox.w)`
- `crown_offset_norm = abs(forehead_center.y - crown.y) / max(1, face_bbox.h)`
- `face_ratio = (face_bbox.w * face_bbox.h) / (image_size.width * image_size.height)`

FE가 같은 값을 로컬에서 계산할 수는 있지만, 판정의 기준은 Inference 계산 결과다.

### 6.5 Feature 메시지

메시지 예시:

```json
{
  "type": "feature",
  "feature_schema_version": 2,
  "coordinate_space": "pixel_v1",
  "anchor_set": "face_anchor_v1",
  "transform_version": "affine_v1",
  "seq": 182,
  "ts_ms": 1710575105123,
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "hair_id": 1,
  "image_size": {
    "width": 430,
    "height": 932
  },
  "pose": {
    "yaw_float": 12.37,
    "pitch_float": -3.18,
    "roll_float": 0.72,
    "yaw_1deg": 12,
    "pitch_1deg": -3,
    "roll_1deg": 1
  },
  "face_bbox": {
    "x": 104,
    "y": 156,
    "w": 216,
    "h": 322
  },
  "anchors": {
    "forehead_center": { "x": 214.501, "y": 193.314, "confidence": 1.0 },
    "left_temple": { "x": 162.412, "y": 221.364, "confidence": 1.0 },
    "right_temple": { "x": 267.587, "y": 220.362, "confidence": 1.0 },
    "crown": { "x": 215.503, "y": 128.185, "confidence": 1.0 },
    "left_ear_root": { "x": 145.880, "y": 255.914, "confidence": 1.0 },
    "right_ear_root": { "x": 283.923, "y": 255.147, "confidence": 1.0 },
    "left_side": { "x": 151.725, "y": 244.115, "confidence": 1.0 },
    "right_side": { "x": 277.912, "y": 243.802, "confidence": 1.0 },
    "lower_left": { "x": 173.435, "y": 395.553, "confidence": 1.0 },
    "lower_right": { "x": 246.566, "y": 394.551, "confidence": 1.0 },
    "neck_left": { "x": 173.435, "y": 432.221, "confidence": 1.0 },
    "neck_right": { "x": 246.566, "y": 431.219, "confidence": 1.0 }
  }
}
```

## 7. 실시간 Backpressure 계약

### 7.1 목표

`seq`로 오래된 응답을 버리는 것만으로는 충분하지 않다. 서버 큐 적체를 막기 위해 세션당 큐 상한을 프로토콜로 고정해야 한다.

### 7.2 세션당 window = 1

세션당 처리 슬롯은 다음 두 개만 허용한다.

- `processing_slot`: 현재 계산 중인 feature 1개
- `pending_slot`: 아직 계산하지 않은 최신 feature 1개

즉, 세션당 backlog 상한은 `1`이다.

### 7.3 FE 송신 규칙

FE는 매 렌더 프레임마다 feature를 만들어도, WS로는 아래 규칙만 따른다.

1. `in_flight`가 없으면 즉시 전송한다.
2. `in_flight`가 있으면 새 feature는 `pending_latest`로 덮어쓴다.
3. 오래된 `pending_latest`는 버린다.
4. Inference가 `processed`를 돌려주면, 그 순간 가장 최신 `pending_latest` 1개만 전송한다.
5. FE는 절대 2개 이상을 소켓 버퍼에 몰아넣지 않는다.

### 7.4 Inference 수신 규칙

Inference는 세션별로 아래 규칙을 강제한다.

1. `processing_slot`이 비어 있으면 즉시 처리 시작
2. 처리 중이면 `pending_slot`을 새 seq로 교체
3. 더 오래된 중간 feature는 즉시 폐기
4. `pending_slot.seq <= last_processed_seq`이면 폐기
5. global overload 시 세션별 추가 적체를 만들지 않고 `drop-and-replace` 유지

### 7.5 응답 규칙

Inference는 asset 변경 여부와 관계없이 각 처리 완료마다 `processed` 메시지를 반환한다.

```json
{
  "type": "processed",
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "accepted_seq": 182,
  "processed_seq": 182,
  "changed": true,
  "asset": {
    "asset_id": "base_pose_bank__yaw+12_pitch-04_roll+00_frame003116",
    "pose_key": "yaw+12_pitch-04_roll+00",
    "score": 7.92
  },
  "queue_depth": 0,
  "dropped_pending_count": 3,
  "overloaded": false
}
```

`changed = false`이면 `asset`을 생략할 수 있다.

`queue_depth` 정의:

- `pending_slot`에 대기 중인 feature 수만 센다.
- `processing_slot`은 포함하지 않는다.
- 따라서 값의 범위는 `0` 또는 `1`이다.

### 7.6 overload 규칙

Inference는 아래 둘 중 하나를 수행해야 한다.

- `throttle` 메시지 전송
- `1013 Try Again Later` close

`throttle` 예시:

```json
{
  "type": "throttle",
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "retry_after_ms": 120,
  "reason": "inference_overloaded"
}
```

FE 동작:

- overlay 렌더는 계속 `15 FPS` 유지
- feature 송신 주기만 일시적으로 낮춘다
- 마지막 확정 asset은 유지한다

### 7.7 liveness와 정지 감지

`processed` 기반 window = 1 구조에서는 응답 유실이나 half-open 연결이 생기면 FE 송신이 영구 정지할 수 있다. 따라서 liveness 규칙을 별도 계약으로 둔다.

#### WebSocket keepalive

- Inference는 `15 s`마다 WebSocket `ping` control frame을 전송한다.
- 브라우저는 native `pong`로 응답한다.
- Inference는 `pong`가 `10 s` 안에 오지 않으면 서버는 `1011`로 close frame을 보내거나 연결을 비정상 종료할 수 있다.
- 이 경우 클라이언트는 비정상 종료를 `1006`으로 관측할 수 있다.

#### application heartbeat

- FE는 최근 `feature` 또는 `processed` 왕복이 `5 s` 이상 없으면 application-level heartbeat를 보낸다.
- 메시지 형식:

```json
{
  "type": "heartbeat",
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "ts_ms": 1710575108123
}
```

- Inference는 아래 응답을 반환한다.

```json
{
  "type": "heartbeat_ack",
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "ts_ms": 1710575108124
}
```

#### processed timeout

- FE는 feature를 전송할 때마다 `processed_timeout_ms` 타이머를 건다.
- same-server 기본값: `250 ms`
- remote inference 기본값: `500 ms`
- timeout 내 `processed` 또는 `throttle`을 받지 못하면 FE는 해당 in-flight를 실패로 간주하고 소켓을 닫은 뒤 resume 절차로 재연결한다.

#### idle session ttl

- Inference는 세션별 마지막 activity 시각을 기록한다.
- `feature`, `heartbeat`, `pong` 중 어느 것도 `30 s` 이상 없으면 session state를 정리하고 연결을 종료할 수 있다.
- 정리 대상:
  - `processing_slot`
  - `pending_slot`
  - hysteresis state
  - smoothing state

#### cleanup 보장

- 정상 close 수신 시 session state 즉시 정리
- idle ttl 만료 시 session state 정리
- node restart 시 in-memory state 폐기 후 Redis 기반 resume 가능 범위만 복구
- cleanup가 끝나면 동일 `apply_session_id`로 stale state를 재사용하지 않는다

## 8. Inference 내부 로직

### 8.1 유지해야 할 `hairddae` 품질 요소

Inference는 `hairddae`의 retrieval score 철학을 그대로 유지해야 한다.

최소 포함 요소:

- `pose yaw/pitch/roll`
- `temple_span_norm`
- `lower_span_norm`
- `crown_offset_norm`
- `face_ratio`

기본 점수식은 `hairddae`의 `retrieval_score()`를 따른다.

- yaw penalty weight: `2.6`
- pitch penalty weight: `1.8`
- roll penalty weight: `1.2`
- temple span ratio weight: `40.0`
- lower span ratio weight: `25.0`
- crown offset ratio weight: `18.0`
- face ratio weight: `18.0`

가중치를 조정할 수는 있지만, 버전 없이 바꾸지 않는다. 변경 시 `retrieval_model_version`을 올린다.

### 8.2 capacity rule

여러 사용자 동시 접속을 고려하면, Inference는 POC처럼 전역 직렬 파이프라인이면 안 된다.

따라서:

- FE가 MediaPipe를 수행하고, Inference는 scoring만 수행한다.
- scoring 대상은 우선 `hair_id`로 강하게 필터링한다.
- full scan이 `p95 <= 3 ms`를 만족하면 유지한다.
- full scan이 느리면 coarse pose bucket pre-index 후 top-K에만 exact score를 적용한다.
- 어떤 경우에도 최종 비교식은 `retrieval_score()`와 동일 버전을 사용한다.

### 8.3 session state

Inference는 session 단위로 다음 상태를 유지한다.

- `last_selected_asset_id`
- `last_selected_score`
- `last_processed_seq`
- `last_sent_seq`
- `last_switch_at_ms`
- `hysteresis_margin`
- `recent_pose_ema`
- `processing_slot`
- `pending_slot`

### 8.4 hysteresis

asset이 너무 자주 바뀌면 부자연스럽다.

따라서 다음 규칙을 둔다.

- 새 asset 점수가 현재 asset보다 `margin` 이상 더 좋을 때만 교체
- 최근 교체 후 최소 유지 시간 보장
- pose가 작은 범위 안에서 흔들릴 때는 기존 asset 유지

## 9. FE Overlay Contract

### 9.1 Canonical Asset Bundle

v2에서 FE가 해석하는 정적 자산 형식은 하나로 고정한다.

- `asset_bundle_schema_version = 1`
- asset index item은 아래 필드를 모두 반드시 가진다.
  - `asset_id`
  - `hair_rgba_url`
  - `hair_mask_url`
  - `anchors_url`
  - `metadata_url`
  - `hair_bbox`
  - `pose_key`
  - `revision`

`v2` FE는 다음을 허용하지 않는다.

- `image_path`와 `hair_rgba_url`의 혼용
- `alpha_path` 별도 해석
- `hair_bbox` 미존재 시 클라이언트 계산 fallback

즉, `hair_bbox`는 asset build 단계에서 미리 계산되어 manifest에 들어가야 한다.

asset index item 예시:

```json
{
  "asset_id": "base_pose_bank__yaw+00_pitch+00_roll+00_frame001234",
  "pose_key": "yaw+00_pitch+00_roll+00",
  "hair_rgba_url": "https://j14m101.p.ssafy.io/static/0001/assets/base_pose_bank__yaw+00_pitch+00_roll+00_frame001234/hair_rgba.png",
  "hair_mask_url": "https://j14m101.p.ssafy.io/static/0001/assets/base_pose_bank__yaw+00_pitch+00_roll+00_frame001234/hair_mask.png",
  "anchors_url": "https://j14m101.p.ssafy.io/static/0001/assets/base_pose_bank__yaw+00_pitch+00_roll+00_frame001234/anchors.json",
  "metadata_url": "https://j14m101.p.ssafy.io/static/0001/assets/base_pose_bank__yaw+00_pitch+00_roll+00_frame001234/metadata.json",
  "hair_bbox": {
    "x": 32,
    "y": 18,
    "w": 418,
    "h": 302
  },
  "revision": "sha256:6f3f2b..."
}
```

### 9.2 preload 규칙

FE preload는 오직 `asset_index_url`의 canonical item만 사용한다.

- preload 대상은 `preload_asset_ids`로 전달한다.
- FE는 preload 시 `hair_rgba_url`, `hair_mask_url`, `anchors_url`, `metadata_url`를 동시에 가져온다.
- first render 경로에서 `hair_mask`로부터 `hair_bbox`를 새로 계산하지 않는다.
- first render 경로에서 bundle schema 해석 분기를 두지 않는다.

### 9.3 `affine_v1` 규칙

FE는 `hairddae` POC와 같은 순서로 transform과 blend를 수행한다.

1. transform point set:
   - `left_temple`
   - `right_temple`
   - `forehead_center`
   - `crown`
2. `estimateAffinePartial2D` 성격의 4-point partial affine 계산
3. 실패 시 첫 3점을 이용한 affine fallback
4. `hair_bbox` 기준 source crop
5. source margin: `16 px`
6. destination margin: `12 px`
7. `rgb`, `alpha`는 linear warp
8. `hair_mask`는 nearest warp
9. `effective_alpha = min(warped_alpha, gaussian_blur(warped_hair_mask, sigma=2.2))`
10. `effective_alpha`에 추가 gaussian blur `sigma=1.8`
11. blend 전에 user ROI를 `10%` darken
12. ROI alpha blend

이 절차가 `affine_v1`이다. 다른 blend 로직은 같은 버전으로 취급하지 않는다.

### 9.4 중요 원칙

- FE와 Inference는 같은 anchor 이름을 사용한다.
- FE와 Inference는 같은 pixel-space를 가정한다.
- FE와 Inference는 같은 `transform_version`을 본다.

즉, selection과 rendering은 분리되지만 좌표계와 버전은 분리되지 않는다.

## 10. Control Plane 계약

### 10.1 `hairapplystart-v2`

현재 구현은 `applySessionId` 중심의 기존 흐름이므로, 새 실시간 계약은 반드시 `v2`로 분리한다.

엔드포인트:

- `POST /api/home/hairapplystart-v2`

요청 예시:

```json
{
  "hair_id": 1,
  "device_id": "ios-safari-7b7f2a6e",
  "client_capabilities": {
    "feature_schema_version": 2,
    "transform_version": "affine_v1"
  }
}
```

응답 예시:

```json
{
  "code": 200,
  "success": true,
  "apply_session_id": "4b9d4f07-1c7f-4de4-a9de-5d8e0f6f5e8d",
  "feature_schema_version": 2,
  "transform_version": "affine_v1",
  "inference": {
    "ws_url": "wss://j14m101.p.ssafy.io/ws/inference/v2/apply",
    "ws_auth_transport": "sec-websocket-protocol.v1",
    "connect_ticket": "signed-short-lived-ticket",
    "expires_at": "2026-03-16T16:00:00Z",
    "node_id": "infer-a-01",
    "processed_timeout_ms": 250,
    "heartbeat_interval_ms": 5000,
    "idle_ttl_ms": 30000
  },
  "static": {
    "base_url": "https://j14m101.p.ssafy.io/static",
    "dataset_code": "0001",
    "asset_bundle_schema_version": 1,
    "asset_index_url": "https://j14m101.p.ssafy.io/static/0001/manifests/asset_index_v0.json",
    "preload_asset_ids": [
      "base_pose_bank__yaw+00_pitch+00_roll+00_frame001234",
      "base_pose_bank__yaw+05_pitch+00_roll+00_frame001310",
      "base_pose_bank__yaw-05_pitch+00_roll+00_frame001188"
    ]
  }
}
```

### 10.2 브라우저 WebSocket 인증 전달 방식

브라우저 WebSocket API는 임의의 `Authorization` 헤더를 붙일 수 없으므로, v2의 ticket 전달 방식은 하나로 고정한다.

선택:

- `Sec-WebSocket-Protocol` 사용

이유:

- 브라우저에서 직접 설정 가능
- query string보다 access log 노출 위험이 낮음
- cross-origin direct WSS에서도 cookie 의존성을 피할 수 있음

클라이언트 생성 규칙:

```ts
new WebSocket(wsUrl, ['hairapply.v2', `ticket.${connectTicket}`]);
```

서버 handshake 규칙:

- `Sec-WebSocket-Protocol` 제안 목록에서 `hairapply.v2`와 `ticket.<jwt>`를 읽는다.
- ticket를 검증한 뒤 서버 응답 subprotocol은 `hairapply.v2` 하나만 선택한다.
- `ticket.` prefix가 없거나 ticket 형식이 잘못되면 handshake를 거절한다.

금지:

- query string token
- cookie 기반 implicit auth
- FE/BE JWT를 inference에 직접 전달

### 10.3 세션 모델

기본 정책은 `user x device 당 1 active apply session`이다.

- 같은 사용자가 다른 디바이스에서 접속하는 것은 허용한다.
- 같은 디바이스에서 새 세션을 시작하면 이전 세션은 종료한다.
- 같은 디바이스의 멀티 탭은 새 세션 생성 대신 기존 세션 재사용 또는 이전 세션 무효화 중 하나로 구현한다.
- 본 문서의 권장안은 `새 요청이 오면 이전 세션 무효화`이다.

### 10.4 ticket trust boundary

Inference 접속 ticket은 본 JWT를 그대로 전달하는 것이 아니라, 별도 short-lived connect ticket이어야 한다.

최소 claim:

- `iss`: BE issuer
- `aud`: `inference`
- `sub`: `user_id`
- `sid`: `apply_session_id`
- `did`: `device_id`
- `hid`: `hair_id`
- `node`: 할당된 inference node id 또는 cluster id
- `ver`: `feature_schema_version`
- `jti`: unique token id
- `iat`, `nbf`, `exp`
- `single_use`: `true`

### 10.5 ticket 검증 규칙

Inference는 connect 시 아래를 모두 검증해야 한다.

- signature 유효
- `aud == inference`
- `sid`, `did`, `hid` 일치
- 현재 연결 node가 `node` claim과 일치
- 만료되지 않음
- `jti`가 재사용되지 않음

재사용 방지:

- `jti`는 Redis에 TTL과 함께 저장
- 첫 성공 handshake 후 consume
- 이미 consume된 `jti`는 거절

### 10.6 reconnect

single-use ticket이므로 연결이 끊기면 FE는 BE로부터 새 resume ticket을 발급받아야 한다.

엔드포인트:

- `POST /api/home/hairapplyresume-v2`

## 11. Inference 상태 복구와 노드 고정

### 11.1 Phase 2: same-server MVP

보장 수준:

- single-node
- in-memory session state
- reconnect는 best-effort

복구 규칙:

- FE는 reconnect 후 새 ticket으로 재접속한다.
- FE는 직전 `last_applied_asset_id`와 최신 feature를 다시 보낸다.
- node restart 시 smoothing buffer와 hysteresis는 초기화될 수 있다.

즉, Phase 2는 품질 검증용이며, 완전한 seamless resume은 보장하지 않는다.

### 11.2 Phase 4: remote inference

보장 수준:

- session-to-node sticky routing
- Redis 기반 session mapping
- 최소 상태 resume 지원

Redis에 저장할 최소 상태:

- `apply_session_id -> node_id`
- `last_processed_seq`
- `last_selected_asset_id`
- `last_selected_score`
- `last_switch_at_ms`
- `recent_pose_ema`
- `updated_at`

복구 규칙:

- reconnect는 기본적으로 같은 node로 라우팅한다.
- node가 죽었으면 새 node를 할당한다.
- 새 node는 Redis snapshot을 읽고 hysteresis 기준 상태를 이어받는다.
- smoothing ring buffer 전체는 보존하지 않아도 되며, EMA 수준의 요약 상태까지만 필수로 본다.

## 12. 배포 토폴로지

### 12.1 현재 단계: same-server

도메인:

- `https://j14m101.p.ssafy.io`

구성:

- FE: same server
- BE: same server
- Inference: same server
- Nginx: same server reverse proxy

라우팅:

- `/` -> FE static
- `/api/*` -> Spring BE
- `/ws/inference/*` -> Inference WebSocket
- `/static/*` -> dataset static files

Docker Compose 서비스:

- `nginx`
- `app`
- `inference`
- `postgres`
- `redis`

### 12.2 다음 단계: inference 분리

추후 GPU 서버 분리 시:

- FE/BE: `j14m101.p.ssafy.io`
- Inference: `infer.j14m101.p.ssafy.io`

동작:

1. FE가 BE의 `hairapplystart-v2` 호출
2. BE가 사용 가능한 inference node 선택
3. FE에 direct WSS URL과 connect ticket 반환
4. FE가 inference 서버와 직접 통신

장점:

- FE <-> Inference hop 감소
- inference 노드 추가가 쉬움
- GPU 서버 수평 확장이 쉬움

## 13. 마이그레이션 계획

### 13.1 현재 상태와의 차이

현재 구현은 아래와 다르다.

- `hairapplystart`는 `v2` 응답을 아직 주지 않는다.
- FE payload는 compact feature v2가 아니다.
- 기존 WS 흐름과 새 inference WS 흐름은 서로 호환되지 않는다.

따라서 덮어쓰기 배포는 금지한다.

### 13.2 공존 전략

추가할 버전드 엔드포인트:

- `POST /api/home/hairapplystart-v2`
- `POST /api/home/hairapplyresume-v2`
- `wss://.../ws/inference/v2/apply`

버전 필드:

- `feature_schema_version = 2`
- `transform_version = affine_v1`

공존 기간의 규칙:

- old FE -> 기존 flow 유지
- new FE -> `v2` flow 사용
- BE와 Nginx는 두 경로를 모두 유지

### 13.3 cutover 조건

아래 조건을 만족하기 전에는 old flow를 제거하지 않는다.

- new FE adoption `>= 95%`
- `steady_state_render_latency p95 <= 66 ms`
- `warm_asset_switch_latency p95 <= 66 ms` on same-server warm path
- `queue_depth p95 == 0`
- critical error rate가 기준 이하

## 14. 관측 가능성, 용량, 리스크

### 14.1 필수 메트릭

#### FE

- `tracking_ms`
- `draw_ms`
- `feature_send_rate`
- `pending_replace_count`
- `asset_cache_hit_rate`
- `bootstrap_latency`

#### Inference

- `process_ms`
- `queue_depth`
- `dropped_pending_count`
- `throttle_count`
- `changed_asset_rate`
- `event_loop_lag_ms`

#### BE

- `hairapplystart_v2_latency`
- `resume_ticket_latency`
- `active_apply_session_count`
- `ticket_replay_reject_count`

### 14.2 리스크: FE overlay 품질 부족

대응:

- `hairddae`의 `affine_v1` 절차를 그대로 TypeScript로 이식
- 품질 비교는 같은 input feature에 대한 overlay diff로 검증
- 필요 시 WebGL 전환

### 14.3 리스크: asset switching 불안정

대응:

- hysteresis
- score margin
- pose EMA smoothing
- same-device session 단일화

### 14.4 리스크: remote inference latency 증가

대응:

- direct FE <-> Inference WSS
- selection loop와 render loop 분리
- overload 시 `drop-and-replace`

### 14.5 리스크: static asset fetch 지연

대응:

- `hairapplystart-v2` 응답에 대표 asset + 인접 pose asset preload 목록 포함
- asset index preload
- 브라우저 메모리 캐시
- cold miss 시 기존 asset 유지

## 15. 로컬 개발과 CI/CD 전략

### 15.1 로컬 우선 개발 원칙

- feature 계약, overlay 품질, backpressure, reconnect, preload는 먼저 로컬에서 검증한다.
- 운영 서버는 실험 환경이 아니므로, 프로토콜/렌더링/버퍼 조정은 운영 서버에서 직접 디버깅하지 않는다.
- 배포는 로컬 검증을 통과한 versioned artifact만 대상으로 한다.

### 15.2 `Inference`를 별도 배포 단위로 본다

same-server MVP 단계라도 `Inference`는 `BE`의 내부 모듈이 아니라 별도 서비스로 취급한다.

이유:

- 코드 루트가 별도 디렉터리(`inference/` 또는 향후 `Inference/`)로 분리된다.
- Docker image가 별도다.
- 장애/롤백/스케일링을 `BE`와 독립적으로 가져가야 한다.
- 다음 단계에서 inference 전용 서버로 이동할 계획이 이미 있다.

따라서 `Inference`는 아래를 별도로 가진다.

- container/service
- image tag/version
- Jenkins pipeline
- deploy step

### 15.3 Jenkins 잡과 트리거 원칙

권장 잡 구성:

- `FE-CD`
- `BE-CD`
- `INFERENCE-CI`
- `INFERENCE-CD`
- `INTEGRATION-SMOKE`

`INFERENCE-CI/CD` 트리거 원칙:

- 기본 브랜치는 `Inference`
- 가능하면 브랜치 조건만 두지 않고 path filter를 함께 둔다.
- 최소 경로:
  - `inference/**`
  - `Inference/**`
  - inference용 `Dockerfile`
  - inference dependency/lock file
  - inference deploy manifest

즉, `Inference` 브랜치 push는 기본 트리거로 쓰되, 문서만 바뀐 경우까지 무조건 배포하지 않도록 경로 조건을 함께 둔다.

### 15.4 same-server MVP 배포 원칙

현재는 `BE`와 `Inference`가 같은 호스트에 배포될 수 있다. 그래도 CD는 분리한다.

- `BE-CD`는 Spring control plane과 Nginx/control-plane 변경을 담당한다.
- `INFERENCE-CD`는 같은 서버의 `inference` 컨테이너만 갱신한다.
- `BE-CD`가 inference 이미지를 암묵적으로 재배포하지 않는다.
- `INFERENCE-CD`가 Spring app를 암묵적으로 재배포하지 않는다.

즉, 같은 서버에 올라도 배포 단위는 하나가 아니다.

### 15.5 inference 서버 분리 시 전환 원칙

다음 단계에서 바뀌는 것은 주로 deploy target host다. 아래 계약은 유지한다.

- `Inference` 브랜치
- inference 전용 Jenkinsfile
- image naming/versioning
- `INFERENCE-CI/CD` job contract
- `hairapplystart-v2` / `resume-v2` / `ws/inference/v2` 프로토콜

즉, same-server MVP는 임시 배치일 뿐이며, 배포 단위 분리 원칙은 지금부터 유지한다.

### 15.6 통합 안전장치

서비스별 CD와 별도로 통합 스모크 체크를 둔다.

실행 시점:

- `BE-CD` 직후
- `INFERENCE-CD` 직후
- Nginx route 또는 compose topology 변경 직후

최소 스모크 체크:

- `POST /api/home/hairapplystart-v2`
- 응답의 `ws_url`, `ws_auth_transport`, `feature_schema_version`, `asset_bundle_schema_version` 검증
- `Sec-WebSocket-Protocol` 기반 handshake 성공
- `asset_index_url` 접근 성공
- feature 1건 전송 후 `processed` 수신

하나라도 실패하면 deploy 성공으로 간주하지 않는다.

## 16. 단계별 구현 계획

### Phase 1. 계약 고정

- `hairapplystart-v2` 응답 정의
- connect ticket / resume ticket 설계
- `feature_schema_version = 2` 고정
- `affine_v1` 고정
- backpressure window = 1 고정
- inference 전용 Jenkinsfile 및 `INFERENCE-CI` 골격 정의
- `INTEGRATION-SMOKE` 체크 항목 고정

### Phase 2. same-server MVP

- `inference/`에 Python ASGI 서비스 생성
- `wss /ws/inference/v2/apply` 구현
- `hairddae` retrieval score 이식
- FE에 compact feature sender 구현
- FE에 `affine_v1` overlay renderer 구현
- same-server 대상 `INFERENCE-CD` 구현
- compose에 inference 서비스 추가
- v2 integration smoke 구현
- same-server warm path 측정

성공 조건:

- `steady_state_render_latency p95 <= 66 ms`
- `warm_asset_switch_latency p95 <= 66 ms`
- `queue_depth p95 == 0`

### Phase 3. 품질 및 운영 보정

- hysteresis tuning
- EMA smoothing tuning
- preload 전략 보정
- cache eviction
- coarse pose bucket pre-index 여부 검증

### Phase 4. remote GPU inference

- inference node registry
- session-to-node allocation
- Redis 기반 session mapping
- resume ticket
- direct FE <-> Inference WSS
- `INFERENCE-CD`의 deploy target을 inference 전용 서버로 전환

## 17. 최종 결론

실서비스 목표를 만족하는 최적 구조는 다음과 같다.

- `BE(Spring)`는 control plane
- `Inference(Python ASGI)`는 feature-based asset selection plane
- `FE`는 final rendering plane

즉:

- `hairddae`의 품질 로직은 유지한다.
- `hairddae`의 프레임 왕복 구조는 버린다.
- `15 FPS`는 FE 로컬 렌더링으로 보장한다.
- selection path는 backpressure와 preload를 통해 same-server warm path에서만 `66 ms` 목표를 가진다.

이 문서의 전제는 다음 한 줄로 요약된다.

> 실서비스에서는 `서버가 asset을 고르고`, `브라우저가 최종 overlay를 그리며`, `큐는 세션당 1개만 남긴다`.
