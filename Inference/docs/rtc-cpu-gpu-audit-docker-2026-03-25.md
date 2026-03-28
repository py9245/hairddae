# RTC CPU/GPU Audit (Docker)

## 기준

- 기준 대상: 도커에서 실행 중인 `inference-server`
- 현재 이미지: `inference-app:rtc-gpu-runtime`
- 현재 주요 환경
  - `INFERENCE_FACE_TRACKER_DELEGATE=gpu`
  - `INFERENCE_HAIR_SEGMENTER_DELEGATE=gpu`
  - `INFERENCE_OPENCV_CUDA_ENABLED=true`
  - `INFERENCE_OPENCV_TORCH_FILTERS_ENABLED=false`
  - `INFERENCE_RTC_RENDERER_NAME=legacy`
  - `INFERENCE_RTC_LIGHTWEIGHT_RENDERER_NAME=legacy`
  - `INFERENCE_RTC_LATENCY_RENDERER_NAME=legacy`

## 한 줄 결론

- 얼굴 랜드마크와 헤어 세그멘테이션은 이미 GPU다.
- OpenCV도 일부는 GPU wrapper를 타고 있다.
- 하지만 RTC 프레임 전체 기준으로 남아 있는 큰 병목은 여전히 CPU다.
- 가장 큰 이유는 두 가지다.
  - 헤어 전환 시 새 에셋 디스크 로드와 디코드
  - blur, morphology, alpha 가공, PIL 합성, PyAV 경계 같은 CPU 중심 구간

## 실제 파이프라인

### 1. RTC 프레임 수신

파일:
- `app/rtc.py`

실행 흐름:
- `source_track.recv()`
- `frame.to_ndarray(format="bgr24")`
- 필요 시 좌우 반전
- 필요 시 처리용 해상도로 축소

상태:
- `frame.to_ndarray()`는 CPU
- `opencv_flip()`, `opencv_resize()`는 큰 프레임이면 GPU 가능

판단:
- 수신 직후의 OpenCV 연산은 이미 꽤 GPU화돼 있다.
- 하지만 PyAV `VideoFrame -> ndarray` 변환은 CPU 경계라서 그대로 남는다.

### 2. 전처리

파일:
- `app/frame_prepare_pipeline.py`
- `app/face_tracking.py`
- `app/hair_segmentation.py`
- `app/hair_attenuation.py`

실행 흐름:
- BGR -> RGB
- 얼굴 랜드마크 추출
- 헤어 세그멘테이션
- 기존 머리 attenuation

상태:
- `opencv_cvt_color()`는 큰 프레임이면 GPU 가능
- 얼굴 랜드마크 MediaPipe는 GPU
- 헤어 세그멘테이션 MediaPipe는 GPU
- 하지만 `hair_attenuation.py`는 여전히 CPU 비중이 크다

`hair_attenuation.py`에서 이미 GPU wrapper를 타는 것:
- `resize`
- `cvtColor`
- `bitwise_and/or/not`
- `addWeighted`
- `gaussian_blur`
- `dilate`
- `erode`

중요:
- 여기서 `gaussian_blur`, `dilate`, `erode`는 현재 도커 env에서 `INFERENCE_OPENCV_TORCH_FILTERS_ENABLED=false`라서 실제로는 CPU다.
- 즉 함수 이름은 wrapper지만, 현재 운영 컨테이너에서는 대부분 CPU fallback이다.

`hair_attenuation.py`에서 아직 raw CPU인 것:
- `cv2.findContours`
- `cv2.connectedComponentsWithStats`
- `cv2.distanceTransform`
- `cv2.morphologyEx`
- `cv2.boundingRect`
- `cv2.subtract`
- `cv2.fillPoly`
- `cv2.fillConvexPoly`
- `cv2.ellipse`
- `cv2.circle`
- `cv2.mean`

판단:
- 전처리에서 MediaPipe 추론은 GPU로 잘 가고 있다.
- 하지만 attenuation의 마스크 후처리와 geometry rasterization은 아직 CPU 중심이다.

### 3. 런타임 선택

파일:
- `app/hairddae_runtime.py`
- `app/hairddae_adapter.py`

실행 흐름:
- 세션 상태 관리
- 후보 asset 선택
- hold / stable / switch 결정
- renderer 결정

상태:
- 거의 전부 pure Python
- GPU 전환 대상이 아님

판단:
- 여기서 느릴 수는 있지만, OpenCV GPU로 옮길 대상은 아니다.
- 이 단계는 구조 최적화 또는 알고리즘 단순화가 답이다.

### 4. asset 로드

파일:
- `hairddae_tools/run_hair_overlay_poc.py`

실행 흐름:
- `load_asset_bundle()`
- metadata JSON
- anchors JSON
- image
- alpha
- hair mask
- face / protect mask

상태:
- 전부 CPU + 디스크 I/O
- `cv2.imread()`와 JSON 로드는 GPU 대상이 아니다

중요:
- 최근 계측 기준으로 `switch` 프레임 병목의 본체는 여기다.
- `asset_load_ms`가 `100ms+`로 잡히고, 실제 warp/alpha/composite는 그보다 훨씬 작다.

판단:
- 현재 도커 기준 가장 큰 지연은 GPU 부족이 아니라 asset load다.
- GPU 최적화만으로는 해결되지 않는다.

### 5. legacy 오버레이 합성

파일:
- `hairddae_tools/run_hair_overlay_poc.py`

실행 흐름:
- affine 추정
- ROI 계산
- RGB / alpha / hair / mask warp
- alpha 생성
- skin suppression
- 최종 합성

현재 GPU wrapper를 타는 것:
- `opencv_warp_affine`
- 일부 `resize`
- 일부 `cvtColor`

하지만 실제 한계:
- warp마다 업로드/다운로드가 반복된다
- 작은 ROI일 때는 `min_pixels` 조건 때문에 CPU fallback으로 갈 수 있다
- `build_effective_alpha()` 내부 blur는 현재 CPU다
- `apply_asset_skin_suppression_gain()` 내부 `smooth_mask_layer()`의 blur/dilate도 현재 CPU다
- `apply_masked_rgb_gain()`의 `convertScaleAbs`와 `copyTo`는 CPU다
- 최종 `composite_effective_layer()`는 NumPy CPU 합성이다

현재 legacy에서 아직 raw CPU인 핵심:
- `cv2.convertScaleAbs`
- `cv2.copyTo`
- `cv2.estimateAffinePartial2D`
- `cv2.getAffineTransform`
- `cv2.transform`

판단:
- legacy는 renderer는 단순하지만, 실제 구현은 완전 GPU 경로가 아니다.
- 특히 blur / morphology / composite가 CPU 중심이라 GPU util이 잘 안 오른다.

### 6. mesh 계열 합성

파일:
- `hairddae_tools/run_hair_overlay_poc.py`

실행 흐름:
- mesh point 생성
- triangle 계산
- triangle별 affine warp
- triangle mask rasterize
- 여러 mask warp
- alpha gain / occlusion gain

상태:
- 일부 `warpAffine`만 GPU wrapper 가능
- 하지만 대부분은 CPU orchestration

raw CPU 핵심:
- `cv2.Subdiv2D`
- `cv2.boundingRect`
- `cv2.getAffineTransform`
- `cv2.fillConvexPoly`
- triangle loop 전체

판단:
- mesh 경로는 OpenCV GPU 몇 개를 붙여도 구조상 CPU가 많이 남는다.
- 진짜 GPU화하려면 `grid_sample`류의 재구성이 필요하다.

### 7. bundle render

파일:
- `app/server_render.py`
- `app/fallback_render_pipeline.py`

실행 흐름:
- RGBA load
- PIL affine transform
- coverage mask 생성
- base ROI 복원
- skin replace
- alpha composite
- paste

상태:
- `opencv_dilate`, `opencv_gaussian_blur`, `opencv_cvt_color` 일부 wrapper 사용
- 하지만 본체는 PIL

raw CPU / PIL 핵심:
- `Image.transform`
- `Image.alpha_composite`
- `Image.paste`
- `_load_rgba_image`
- `_load_mask_image`

판단:
- bundle render는 현재 GPU 경로가 아니다.
- 큰 구조 변경 없이는 GPU 활용이 오르지 않는다.

### 8. overlay postprocess

파일:
- `app/overlay_postprocess_pipeline.py`

상태:
- `absdiff`, `bitwise`, `dilate`, `gaussian_blur`는 wrapper 사용
- 하지만 `boundingRect`는 CPU
- 그리고 blur/dilate는 현재 env 기준 CPU fallback

판단:
- 경량이지만 완전 GPU는 아니다.

### 9. 인코드 및 RTC 재송신

파일:
- `app/hairddae_runtime.py`
- `app/rtc.py`

실행 흐름:
- `cv2.imencode(".jpg", ...)`
- `VideoFrame.from_ndarray(...)`

상태:
- 둘 다 CPU

판단:
- 이 구간은 OpenCV CUDA로 해결되지 않는다.
- PyAV / codec 경계라 구조 변경이 필요하다.

## 지금 도커에서 실제로 GPU인 것

- MediaPipe face landmarker
- MediaPipe hair segmenter
- OpenCV wrapper 중 큰 입력에서 조건을 만족하는:
  - `resize`
  - `flip`
  - `cvtColor`
  - `warpAffine`
  - `addWeighted`
  - `absdiff`
  - `bitwise_and/or/not`
  - `min`

## 지금 도커에서 wrapper는 있지만 실제로 CPU인 것

현재 이유:
- `INFERENCE_OPENCV_TORCH_FILTERS_ENABLED=false`

영향 받는 함수:
- `opencv_gaussian_blur`
- `opencv_dilate`
- `opencv_erode`

즉 현재 운영 도커에서는 이 세 개가 wrapper 이름을 갖고 있어도 대부분 CPU fallback이다.

## 지금 바로 GPU 전환 후보

### 1. 비교적 안전한 후보

- `INFERENCE_OPENCV_TORCH_FILTERS_ENABLED` 검증 후 활성화
  - 대상:
    - `app/hair_attenuation.py`
    - `app/overlay_postprocess_pipeline.py`
    - `app/server_render.py`
    - `hairddae_tools/run_hair_overlay_poc.py`
    - `hairddae_tools/realtime_face_parsing.py`
  - 기대 효과:
    - blur / dilate / erode 일부를 Torch CUDA로 우회 가능
  - 리스크:
    - 운영 안정성 재검증 필요

- `legacy` 경로에서 GPU 업로드/다운로드 횟수 줄이기
  - 현재는 `warp`마다 업로드/다운로드
  - `rgb`, `alpha`, `hair`, `mask stack`을 GPU 메모리에 한 번 올리고 마지막에만 내리는 구조로 바꾸는 게 더 중요

- `apply_masked_rgb_gain()` GPU화
  - 현재 `convertScaleAbs + copyTo`는 CPU
  - mask 기반 gain 적용을 GPU 행렬 연산으로 재작성 가능

- `composite_effective_layer()` GPU화
  - 현재 NumPy float blend
  - ROI 단위 alpha blend를 GPU로 계산하고 마지막에만 download 가능

### 2. 중간 난도 후보

- `load_asset_bundle()` 이후 디코드된 asset를 GPU-friendly 포맷으로 유지
- `server_render.py`의 YCrCb 변환과 skin replace ROI를 GPU mat 흐름으로 묶기
- `realtime_face_parsing.py`의 raw bitwise 일부를 wrapper로 통일

### 3. 구조를 바꿔야 하는 후보

- `cv2.distanceTransform`
- `cv2.connectedComponentsWithStats`
- `cv2.findContours`
- `cv2.Subdiv2D`
- triangle mesh rasterization
- PIL `Image.transform / alpha_composite / paste`
- `cv2.imencode`
- `VideoFrame.to_ndarray / from_ndarray`

이들은 단순 wrapper 교체로는 안 된다.

## 우선순위 정리

현재 목표가 `기능 유지 + stable 성능 유지 + 그 다음 동시접속`이면 우선순위는 이 순서가 맞다.

1. `load_asset_bundle` 최적화
   - 지금 switch 지연의 본체
   - GPU보다 먼저 잡아야 한다

2. blur / morphology를 실제 GPU로 보내는 경로 검증
   - 현재 숨겨진 후보는 Torch CUDA filters

3. legacy 합성에서 upload/download 최소화
   - 개별 wrapper 호출보다 중요하다

4. composite와 tone gain 같은 ROI 연산 GPU화

5. bundle/PIL/mesh 구조는 마지막
   - 공수가 가장 크다

## 실무 판단

- 지금 도커 기준으로 “CPU -> GPU 할 수 있는 것”은 아직 남아 있다.
- 하지만 남은 큰 것들은 대부분 “wrapper 하나 더” 수준이 아니다.
- 진짜 효과를 내려면
  - blur / morphology를 실제 GPU로 보내고
  - legacy overlay에서 GPU 메모리 재사용 구조를 만들고
  - asset load 병목은 별도로 줄여야 한다.

- 다시 말해:
  - 현재 GPU가 노는 이유는 “GPU를 전혀 안 써서”만은 아니고
  - “CPU/디스크 병목이 먼저 있고, GPU 호출도 너무 잘게 쪼개져 있기 때문”이다.
