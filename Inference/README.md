# HairApply Inference Execution Map

이 문서는 `Inference` 서비스가 실제로 어떻게 시작되고, 어떤 모듈을 거쳐 요청을 처리하는지 E2E 기준으로 정리한 운영 메모다.

기준 시점: 2026-03-24

## 1. 시작 지점

### 컨테이너/프로세스 시작 순서

1. `docker-compose.gpu.yml`
   `inference-server` 컨테이너를 띄우고 `/app/.venv/bin/python -m uvicorn app.main:create_app --factory`를 실행한다.
2. `Dockerfile`
   런타임 이미지를 만들고 `app/`, `hairddae_tools/`, `models/`를 이미지에 복사한다.
3. `app/main.py`
   `create_app()`가 FastAPI 앱을 만들고, 설정/런타임 의존성/라우트를 모두 연결한다.

### `create_app()`에서 실제로 연결하는 모듈

- `app/config.py`
  환경변수를 읽어 `Settings`를 만들고 모델 경로, static root, RTC/HTTP 옵션을 결정한다.
- `app/rtc_udp_port_range.py`
  `aioice` UDP 바인딩을 지정 포트 범위로 제한한다.
- `app/auth.py`
  replay store를 구성한다.
- `app/catalog.py`
  asset catalog 로더를 준비한다.
- `app/lazy_runtime_dependencies.py`
  face tracker, hair segmenter, hair attenuator를 lazy init 래퍼로 준비한다.
- `app/hairddae_runtime_manager.py`
  dataset별 `HairOverlayRuntime` 캐시를 관리한다.
- `app/http_runtime.py`
  HTTP 테스트/렌더링 라우트를 등록한다.
- `app/rtc.py`
  WebRTC offer, control channel, video frame 처리 라우트를 등록한다.

## 2. E2E 흐름

### HTTP 프레임 경로

`docker-compose.gpu.yml`
-> `app.main:create_app`
-> `app.http_runtime:attach_http_runtime_routes`
-> `/api/runtime/frame` 또는 `/api/runtime/render-frame`
-> `app.http_runtime:_process_http_frame`
-> `app.hairddae_runtime_manager.HairddaeRuntimeManager.process_frame`
-> `app.hairddae_runtime.HairOverlayRuntime.process_frame`
-> 결과 JPEG/PNG 응답

이 경로에서 핵심 하위 모듈은 다음과 같다.

- `app/hairddae_runtime_manager.py`
  dataset별 runtime을 캐시하고 face parsing repo/weights/env를 맞춘다.
- `app/hairddae_runtime.py`
  세션 상태, 얼굴 feature 추출, 사용자 parsing, asset 선택, 합성을 한 번에 처리하는 핵심 엔진이다.
- `app/server_render.py`
  RGBA hair asset을 frame에 affine warp 후 합성한다.
- `app/overlay_postprocess_pipeline.py`
  합성 뒤 coverage/mask 기반 후처리를 적용한다.

### RTC offer + 영상 프레임 경로

`docker-compose.gpu.yml`
-> `app.main:create_app`
-> `app.rtc:attach_rtc_routes`
-> `/rtc/offer`
-> `app.auth.validate_connect_ticket`
-> `app.rtc._create_peer_connection`
-> data channel/control message 처리
-> incoming video track에 `RtcServerTrackedRenderTrack` 연결
-> `RtcServerTrackedRenderTrack.recv()`
-> `app.frame_prepare_pipeline.prepare_runtime_frame`
-> `app.hairddae_runtime_manager.HairddaeRuntimeManager.process_frame`
-> `app.hairddae_runtime.HairOverlayRuntime.process_frame`
-> processed video frame 반환

RTC 프레임 준비 단계에서 쓰는 하위 모듈:

- `app/face_tracking.py`
  MediaPipe face landmarker로 pose, anchors, bbox, feature payload를 만든다.
- `app/hair_segmentation.py`
  hair confidence mask를 만든다.
- `app/hair_attenuation.py`
  사용자 원본 머리 영역을 attenuation/bald 처리해 overlay가 더 안정적으로 보이게 만든다.
- `app/frame_prepare_pipeline.py`
  tracking + segmentation을 병렬 수행하고, 결과를 이용해 prepared frame을 만든다.
- `app/fallback_render_pipeline.py`
  런타임 경로가 아닌 catalog 기반 단순 합성 fallback을 제공한다.

### Asset 선택/합성 내부 흐름

`app.hairddae_runtime.HairOverlayRuntime.process_frame`
-> 얼굴 feature 확보
-> 사용자 parsing/mask 재사용 판단
-> asset 선택
-> render/composite
-> overlay postprocess

이 단계에서 쓰는 모듈:

- `app/catalog.py`
  dataset manifest를 읽고 `AssetBundle`을 만든다.
- `app/hairddae_adapter.py`
  `hairddae_tools`의 선택 로직을 app 런타임에 맞게 감싼다.
- `app/render.py`
  asset anchor와 사용자 anchor로 affine render task를 만든다.
- `app/server_render.py`
  실제 이미지 warp/composite를 수행한다.
- `app/models.py`
  feature payload의 pydantic 모델을 정의한다.

## 3. `app/` 파일별 역할

| Path | 역할 | 누가 사용하나 |
| --- | --- | --- |
| `app/main.py` | FastAPI app factory, dependency wiring, lifespan cleanup | Uvicorn 엔트리포인트 |
| `app/config.py` | 환경변수 -> `Settings` 구성 | `main`, `rtc`, `http_runtime`, `auth`, `catalog`, `runtime_manager` |
| `app/rtc_udp_port_range.py` | `aioice` UDP 바인딩 범위 patch | `main` |
| `app/auth.py` | connect ticket 검증, replay 방지 | `main`, `rtc`, `face_tracking` |
| `app/http_runtime.py` | HTTP health/frame/render-frame 라우트 | `main` |
| `app/rtc.py` | RTC offer, control channel, video processing loop | `main` |
| `app/lazy_runtime_dependencies.py` | tracking/segmentation/attenuation lazy init | `main` |
| `app/face_tracking.py` | 얼굴 landmark, pose, anchor, bbox 추출 | `lazy_runtime_dependencies`, `rtc`, `hair_attenuation` |
| `app/hair_segmentation.py` | MediaPipe hair confidence mask 생성 | `lazy_runtime_dependencies` |
| `app/hair_attenuation.py` | 원본 머리 suppression/attenuation | `lazy_runtime_dependencies`, `rtc` |
| `app/frame_prepare_pipeline.py` | RTC 입력 프레임 사전 처리 | `rtc` |
| `app/fallback_render_pipeline.py` | catalog 기반 fallback render | `rtc` |
| `app/hairddae_runtime_manager.py` | dataset별 runtime cache와 env 준비 | `main`, `rtc`, `http_runtime` |
| `app/hairddae_runtime.py` | 핵심 세션/선택/합성 엔진 | `hairddae_runtime_manager` |
| `app/catalog.py` | asset index 로드, bundle 생성, control target 검증 | `main`, `rtc`, `fallback_render_pipeline` |
| `app/hairddae_adapter.py` | `hairddae_tools` 선택 함수 bridge | `catalog` |
| `app/render.py` | affine render task 계산 | `catalog`, `hairddae_runtime` |
| `app/server_render.py` | image warp/composite/coverage restore | `rtc`, `fallback_render_pipeline`, `hairddae_runtime` |
| `app/overlay_postprocess_pipeline.py` | overlay 결과 후처리 | `hairddae_runtime` |
| `app/models.py` | feature message schema | `face_tracking`, `render`, `catalog`, `rtc`, `fallback_render_pipeline`, `hairddae_runtime`, `hairddae_adapter`, `frame_prepare_pipeline` |
| `app/__init__.py` | package marker | Python import system |

## 4. `hairddae_tools/` 중 런타임에서 실제로 물고 있는 파일

아래 파일은 app 런타임이 직접 import하거나 실질적으로 의존한다.

| Path | 역할 | 누가 사용하나 |
| --- | --- | --- |
| `hairddae_tools/run_hair_overlay_poc.py` | asset ranking, best asset selection, overlay helper | `app/hairddae_adapter.py`, `app/hairddae_runtime.py` |
| `hairddae_tools/face_feature_utils.py` | MediaPipe landmarker 생성과 feature 추출 | `app/hairddae_runtime.py` |
| `hairddae_tools/realtime_face_parsing.py` | user face/hair parsing runtime | `app/hairddae_runtime.py` |
| `hairddae_tools/local_demo_paths.py` | runtime/static/generated 경로 해석 | `app/hairddae_runtime.py`, 여러 active tool |

운영상 같이 기억해야 하는 offline/build 스크립트:

- `hairddae_tools/build_local_demo_assets.py`
  runtime이 읽는 asset index/manifest류를 만드는 준비 스크립트다.

## 5. 현재 정리 상태

### `app/`

2026-03-24 기준 `app/*.py`는 모두 repo 내부에서 참조가 확인됐다. 즉, 지금은 archive로 뺀 파일이 없다.

### `hairddae_tools/`

repo 내부 참조가 없던 스크립트는 `hairddae_tools/archive/`로 이동했다. active tool set은 루트에 남아 있다.

## 6. 운영자가 먼저 보면 좋은 파일

1. `docker-compose.gpu.yml`
2. `app/main.py`
3. `app/rtc.py`
4. `app/http_runtime.py`
5. `app/hairddae_runtime_manager.py`
6. `app/hairddae_runtime.py`
7. `app/catalog.py`
8. `app/server_render.py`

## 7. CUDA OpenCV

로컬 `.venv`와 Docker 이미지 모두 기본 wheel OpenCV 위에 CUDA 빌드 바이너리를 overlay해서 사용한다.

- 로컬 설치: `./scripts/install_opencv_cuda_local.sh`
- 로컬 확인: `./.venv/bin/python scripts/inspect_opencv_cuda.py`
- Docker 빌드: `docker compose -f docker-compose.gpu.yml build inference`

주의:

- `docker-compose.gpu.yml`은 `/app/.venv`를 별도 volume으로 유지한다. 이미지에 bake된 CUDA OpenCV가 호스트 `.venv` bind mount에 가려지지 않게 하기 위한 설정이다.
- 이미지 안 `.venv`를 새로 받으려면 기존 volume을 지우고 다시 올려야 한다.
  예: `docker compose -f docker-compose.gpu.yml down -v && docker compose -f docker-compose.gpu.yml up -d`


## 7. BE 데이터 등록 API 양식
  curl -X POST 'https://hairddae.store/api/internal/hairs/sync/' \
    -H 'X-Inference-Sync-Secret: <APP_INFERENCE_METADATA_SYNC_SECRET>' \
    -F 'dataset_code=0001' \
    -F 'name=leaf cut' \
    -F 'slug=leaf-cut' \
    -F 'category=short' \
    -F 'description=Hair dataset imported from static asset pack 0001.' \
    -F 'dataset_root_url=/static/0001' \
    -F 'asset_index_url=/static/0001/manifests/asset_index_v0.json' \
    -F 'representative_asset_id=base_pose_bank__yaw+00_pitch+01_roll-01_frame000922' \
    -F 'preview_image_url=/static/0001/hair_rgba/base_pose_bank__yaw+00_pitch+01_roll-
  01_frame000922.png' \
    -F 'active=true'
