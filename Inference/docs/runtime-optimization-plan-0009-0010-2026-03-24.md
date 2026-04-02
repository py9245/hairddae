# 0009 / 0010 런타임 최적화 계획

## 목표

- 대상 데이터셋: `0009`, `0010`
- 목표: 현재 RTC 처리 기준 `processing p50`을 `150~161ms` 수준에서 `80ms` 근처까지 낮추기
- 우선순위:
  1. `0009`를 먼저 `80ms` 근처까지 내리기
  2. `0010`을 `90ms 이하`까지 먼저 안정화한 뒤 `80ms` 근처까지 추가 압축

중요:

- 현재 `rtc total`은 순수 처리시간이 아니다.
- [app/rtc.py](../app/rtc.py) `1071-1073`에서 타이머가 시작된 뒤 `_next_latest_frame()`을 기다리므로, 프레임 대기시간이 섞인다.
- 따라서 성능 목표는 아래 두 지표로 분리해서 봐야 한다.
  - `frame_wait_ms`: 프레임 대기 / 스케줄링 지연
  - `processing_total_ms`: 디코드 이후 실제 처리 시간

이 문서의 핵심 비교 기준은 `processing_est_p50`이다.

## 현재 기준선

최근 로그 기준 추정치:

| 데이터셋 | rtc total p50 | prepare wall p50 | hair_overlay p50 | processing_est p50 |
|---|---:|---:|---:|---:|
| `0009` | `168.2ms` | `36.7ms` | `112.5ms` | `151.7ms` |
| `0010` | `166.7ms` | `38.4ms` | `125.1ms` | `160.8ms` |

여기서:

- `prepare wall p50 = resize_in + max(tracking, segmentation) + attenuation`
- `processing_est p50 = prepare wall + hair_overlay + resize_out`

즉 현재는 `prepare`보다 `overlay`가 확실한 주병목이다.

## 호출 구조

### 1. RTC 입력

- [app/rtc.py](../app/rtc.py) `1070-1165`
- 주요 역할
  - 최신 프레임 가져오기
  - 디코드
  - 처리용 크기로 resize
  - 전처리 / 런타임 호출
  - 실패 시 fallback

핵심 포인트:

- `frame_started_at`가 `_next_latest_frame()`보다 먼저 시작된다.
- 그래서 지금 `total`에는 프레임 대기시간이 포함된다.

### 2. 전처리

- [app/frame_prepare_pipeline.py](../app/frame_prepare_pipeline.py) `49-239`
- 주요 역할
  - `tracking`
  - `hair segmentation`
  - `hair attenuation`

핵심 포인트:

- `tracking`과 `segmentation`은 [app/frame_prepare_pipeline.py](../app/frame_prepare_pipeline.py) `96-99`에서 병렬 실행된다.
- 따라서 wall time은 `tracking + segmentation`이 아니라 `max(tracking, segmentation)`에 가깝다.

### 3. 런타임 선택 / 합성

- [app/hairddae_runtime.py](../app/hairddae_runtime.py) `2807-3110`
- 내부 큰 흐름
  - `_smooth_user_row`
  - `_parse_user_masks`
  - `_attach_runtime_fit_context`
  - `_select_and_compose_output_frame`

세부 선택 경로:

- [app/hairddae_runtime.py](../app/hairddae_runtime.py) `2059-2145`
  - `_select_asset`
- [app/hairddae_runtime.py](../app/hairddae_runtime.py) `1661-1763`
  - `_build_blend_assets`
- [app/hairddae_runtime.py](../app/hairddae_runtime.py) `2322-2408`
  - `_compose_output_frame`

### 4. 실제 overlay 본체

- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2502-2542`
  - `compose_overlay_blend_frame`
- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2430-2460`
  - `_compose_mesh_blend_frame_from_active_assets`
- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2405-2427`
  - `_build_mesh_weighted_layers`
- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2114-2326`
  - `build_mesh_overlay_layer`

이 경로가 현재 `0009`, `0010`의 핵심 병목이다.

### 5. fallback

- [app/rtc.py](../app/rtc.py) `1107-1165`
- overlay 결과가 `overlay_error`이거나 asset 미결정이면 `bundle_render_fallback`으로 다시 들어간다.

현재:

- `0009`는 최근 로그상 fallback 없이 정상권
- `0010`은 여전히 일부 asset에서 render failure / fallback 잔존

## 현재 병목 정리

### 전처리 병목 아님

`0009` p50:

- `resize_in`: `2.9ms`
- `tracking`: `26.3ms`
- `segmentation`: `26.6ms`
- `attenuation`: `7.8ms`
- `prepare wall`: `36.7ms`

`0010` p50:

- `resize_in`: `2.0ms`
- `tracking`: `25.7ms`
- `segmentation`: `26.0ms`
- `attenuation`: `8.0ms`
- `prepare wall`: `38.4ms`

즉 현재 80ms 목표를 막는 주된 이유는 MediaPipe보다 overlay다.

### overlay 상세 로그

`0009`

- `select_and_compose_ms p50`: `112.4ms`
- `overlay_total_ms p50`: `112.5ms`
- `overlay_blend_ms p50`: `111.2ms`
- `resolve_compose_mode_ms p50`: `0.001ms`
- `resolve_compose_renderer_ms p50`: `0.004ms`

`0010`

- `select_and_compose_ms p50`: `129.0ms`
- `overlay_total_ms p50`: `129.1ms`
- `overlay_blend_ms p50`: `126.6ms`
- `resolve_compose_mode_ms p50`: `0.001ms`
- `resolve_compose_renderer_ms p50`: `0.005ms`

의미:

- 선택 정책 계산 자체는 느리지 않다.
- 거의 전부 `overlay_blend_ms`에서 쓰고 있다.

## 실제 함수 단위 측정

### 1. `load_asset_bundle()` vs `build_mesh_overlay_layer()`

대표 자산 기준 로컬 함수 측정:

| 데이터셋 | `load_asset_bundle` miss | `load_asset_bundle` hit p50 | `build_mesh_overlay_layer` p50 |
|---|---:|---:|---:|
| `0009` | `101.89ms` | `0ms` | `53.09ms` |
| `0010` | `100.87ms` | `0ms` | `80.28ms` |

해석:

- 캐시 miss는 여전히 매우 비싸다.
- 다만 steady-state에서 더 큰 병목은 `build_mesh_overlay_layer()` 자체다.
- 즉 디스크 문제보다 `mesh overlay 계산`이 더 중요하다.

### 2. `build_mesh_overlay_layer()` 내부 상대 비용

대표 자산 기준 계측.
주의: 아래 일부 함수는 서로 중첩 호출이라 합산값으로 해석하면 안 되고, 상대적 무게만 봐야 한다.

`0009`

- `total`: `48.27ms`
- `warp_mesh_layer`: `33.68ms`
- `warp_cropped_mask_layer`: `11.98ms`
- `build_effective_alpha`: `2.35ms`
- `build_mesh_v2_alpha_gain`: `1.33ms`
- `apply_asset_skin_suppression_gain`: `8.84ms`
- `estimate_transform`: `0.07ms`
- `compute_conservative_head_size_scale`: `0.01ms`
- `mesh_distortion_metrics`: `0.25ms`

`0010`

- `total`: `83.39ms`
- `warp_mesh_layer`: `61.06ms`
- `warp_cropped_mask_layer`: `14.93ms`
- `build_effective_alpha`: `3.66ms`
- `build_mesh_v2_alpha_gain`: `2.53ms`
- `apply_asset_skin_suppression_gain`: `12.30ms`
- `estimate_transform`: `0.08ms`
- `compute_conservative_head_size_scale`: `0.01ms`
- `mesh_distortion_metrics`: `0.25ms`

결론:

- 진짜 비싼 건 `transform 추정`이나 `선택`이 아니다.
- 거의 전부 `warp_mesh_layer`와 suppression 계열이다.

## 왜 규칙기반인데 느린가

현재 `mesh_v2` 한 자산 기준 핵심 작업:

- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2208-2210`
  - `RGB`, `alpha`, `hair_mask`를 각각 `warp_mesh_layer`
- [hairddae_tools/run_hair_overlay_poc.py](../hairddae_tools/run_hair_overlay_poc.py) `2216-2247`
  - `face`, `protect_face`, `ear_left`, `ear_right`를 각각 `warp_cropped_mask_layer`

즉 현재 `mesh_v2`는 한 자산당 최소:

- 메인 warp `3회`
- suppression mask warp `4회`

를 수행한다.

추가 사실:

- `mesh_v2 control point` 수: `20`
- 대표 샘플 기준 `point` 수: `36`
- 대표 샘플 기준 triangle 수:
  - `0009`: `42~54`
  - `0010`: 거의 `54`

즉 대략 한 자산 한 프레임에 `54 triangle x 7 pass` 수준의 patch warp가 발생한다.

이건 “조건문 몇 개”가 아니라 사실상 작은 이미지 처리 파이프라인이다.

## 0009 / 0010 데이터셋 차이

### 0009

- asset 수: `3617`
- 최근 feature 프레임: `69`
- unique asset: `37`
- `switch`: `40`
- `stable`: `22`
- `hold`: `3`
- `hold_deadband`: `3`

대표 속성:

- `hair_rgba_bbox ratio p50`: `0.1006`
- `face_overlap_ratio p50`: `0.005927`

해석:

- 0009는 자산이 많지만, 얼굴 겹침 위험은 낮은 편이다.
- 현재 suppression mask 4개를 매번 warp하는 비용 대비 안전성 이득이 낮다.

### 0010

- asset 수: `1926`
- 최근 feature 프레임: `76`
- unique asset: `47`
- `switch`: `51`
- `stable`: `10`
- `stable_pitch_band`: `4`
- fallback 이력 있음

대표 속성:

- `hair_rgba_bbox ratio p50`: `0.1272`
- `face_overlap_ratio p50`: `0.007034`

해석:

- 0010은 0009보다 bbox가 커서 warp 비용이 더 높다.
- suppression 필요성은 0009보다 조금 높지만, 현재 4-mask warp 구조는 여전히 무겁다.

## 직접 단순화 실험

### 1. mask suppression 제거

대표 자산 기준:

| 데이터셋 | baseline `mesh_v2` | suppression 제거 | 절감 |
|---|---:|---:|---:|
| `0009` | `48.51ms` | `27.99ms` | `-20.52ms` |
| `0010` | `83.32ms` | `55.87ms` | `-27.45ms` |

의미:

- 지금 구조에서 가장 먼저 깎아야 할 건 suppression 쪽이다.
- `alpha_gain` 자체는 거의 의미가 없었다.

### 2. `build_mesh_v2_alpha_gain` 제거

대표 자산 기준:

| 데이터셋 | baseline | alpha gain 제거 | 절감 |
|---|---:|---:|---:|
| `0009` | `48.51ms` | `47.50ms` | `-1.01ms` |
| `0010` | `83.32ms` | `82.13ms` | `-1.19ms` |

의미:

- `alpha gain`은 성능 관점 우선순위가 낮다.
- 품질 조정용이지 성능 병목은 아니다.

### 3. 완전한 affine legacy 경로

대표 자산 기준:

| 데이터셋 | `compose_overlay_legacy_frame` |
|---|---:|
| `0009` | `18.19ms` |
| `0010` | `59.45ms` |

중요:

- 현재 runtime의 `mesh_v1`은 이 싼 affine 경로가 아니다.
- 실제로 `mesh_v1`은 오히려 `mesh_v2`보다 느렸다.
- 따라서 저비용 대안이 필요하면 **새 renderer를 따로 만들어야 한다.**

## 지금 당장 손대야 할 것

## 1단계: 측정 정의 수정

목적:

- 80ms 목표를 현실적으로 추적하기 위해서다.

작업:

- `app/rtc.py`
  - `frame_wait_ms`
  - `processing_total_ms`
  - `prepare_wall_ms`
  - `overlay_only_ms`
  - `encode_ms`
  - `fallback_ms`
  를 분리 로그로 남긴다.

기대효과:

- 절감량 판단이 정확해진다.
- 실제로 80ms에 가까운지, wait 때문에 커 보이는지 분리된다.

절감량:

- 직접 성능 개선은 거의 없음
- 하지만 이후 최적화 판단 정확도는 크게 올라감

## 2단계: 0009 전용 경량화

핵심 가설:

- `0009`는 얼굴 겹침 위험이 낮고 suppression 비용이 과하다.

작업:

1. `mesh_v2`에서 `face/protect/ear` 4-mask warp 제거
2. `apply_asset_skin_suppression_gain` 비활성
3. `single asset only` 유지
4. switch deadband / hold 강화
5. 초기 `top-k` 인접 asset prewarm

예상 효과:

- suppression 제거만으로 overlay 기준 `20ms+`
- churn 감소와 prewarm까지 합치면 steady-state `10~15ms`
- 합산 기대:
  - `0009 overlay p50`: `112.5ms -> 75~90ms`
  - `0009 processing p50`: `151.7ms -> 110ms 안팎`

이 단계만으로는 80ms에 닿지 않을 수 있다.

## 3단계: 0009 전용 affine_fast renderer 추가

핵심 가설:

- `0009`는 mesh 변형 없이 affine 수준으로도 품질이 버틸 수 있다.

작업:

1. `mesh_v1` 재사용 금지
2. `compose_overlay_legacy_frame()` 계열을 runtime renderer로 승격
3. renderer 이름을 예: `affine_fast_v1`로 분리
4. `0009`는 기본 renderer를 `affine_fast_v1`
5. extreme yaw/pitch에서만 `mesh_v2_lite`로 승격

예상 효과:

- 대표 자산 기준 `18ms`
- 실제 런타임 기준으로도 overlay를 `35~50ms`대까지 낮출 가능성이 큼
- `prepare 36.7ms + overlay 35~50ms + 기타 5~8ms`
  - `0009 processing total`: `77~95ms`

즉 0009는 이 경로가 80ms 목표의 가장 현실적인 해법이다.

## 4단계: 0010 suppression 구조 단순화

핵심 가설:

- 0010은 suppression을 아예 없애기엔 리스크가 있지만, 4-mask warp는 과하다.

작업:

1. `face_mask`, `protect_face_mask`, `ear_left`, `ear_right`를 런타임에서 따로 warp하지 말고
2. offline에서 하나의 `combined_suppression_mask`로 합친다
3. runtime에서는 suppression mask warp를 `1회`만 수행한다
4. `apply_asset_skin_suppression_gain`는 combined mask 기준으로만 적용

기대효과:

- 현재 suppression 전체 upper bound는 `27ms`
- 그중 절반 이상 회수 가능
- 보수적으로 `12~18ms` 절감 기대

예상 결과:

- `0010 overlay p50`: `125.1ms -> 105~113ms`

## 5단계: 0010 전용 mesh_lite_v2 추가

핵심 가설:

- 0010은 affine까지 내리면 품질 저하가 커질 수 있으므로, 메쉬는 유지하되 triangle 수를 줄여야 한다.

현재:

- mesh_v2는 point `36`, triangle `54`

제안:

- `mesh_lite_v2`
  - control point 축소
  - boundary point 축소
  - triangle 수를 `24~30` 수준으로 낮춤
  - pass는 `RGB`, `alpha`, `hair`, `combined_suppression_mask`만 유지

예상 효과:

- `warp_mesh_layer`가 현재 0010 대표 자산에서 `61ms`
- triangle 수를 절반 수준으로 낮추면 `20~30ms` 회수 가능성이 높다

예상 결과:

- `0010 overlay p50`: `125.1ms -> 75~95ms`

## 6단계: 0010 고비용 asset에만 affine_fast fallback

적용 조건 예:

- `render_cost_ratio` 상위 구간
- bbox ratio 상위 구간
- 반복 render failure asset
- extreme yaw/pitch가 아닌 구간

의도:

- 전체 0010을 affine로 바꾸는 게 아니라, 가장 비싼 일부 asset만 affine_fast로 우회

기대효과:

- p95, outlier, fallback 감소
- `0009`만큼은 아니어도 `0010`을 `80~90ms`대로 끌어내릴 가능성 있음

## 7단계: selection churn 억제

selection 계산 자체는 느리지 않다.
하지만 asset churn은 `cache miss`, `cold bundle load`, `visual jitter`를 만든다.

작업:

1. dataset별 hold 파라미터 분리
2. `0009`: `switch` 기준 더 보수적으로
3. `0010`: `pitch_band`, `safe_asset`, `render_cost` 우선순위를 더 강하게
4. `select_hair` 이후 인접 pose asset prewarm

실제 로그 기준 churn:

- `0009`: `69 frame / 37 unique asset`
- `0010`: `76 frame / 47 unique asset`

이건 너무 많다.

목표:

- `0009`: 70 frame 기준 unique asset `15~20` 수준
- `0010`: 80 frame 기준 unique asset `20~25` 수준

절감량:

- p50보다는 p95 / 초기 spike 개선 효과가 큼

## 8단계: dataset switch stale-state 차단

최근 로그에 남은 이슈:

- `unknown asset_id ... for dataset 0010`
- `unknown asset_id ... for dataset 0009`

현재 [app/rtc.py](../app/rtc.py) `483-485`에서 dataset switch 시 `reset_session()`을 호출하지만, in-flight frame 한 장이 이전 dataset asset id를 들고 들어올 가능성이 남아 있다.

작업:

1. `select_hair`마다 `target_epoch` 증가
2. frame 처리 시작 시 epoch snapshot 저장
3. 처리 완료 시 현재 epoch와 다르면 결과 폐기
4. fallback / bundle build에도 epoch 전달

이건 주된 p50 병목은 아니지만, `0010`의 잔여 fallback / stale asset 문제를 줄이는 correctness 수정이다.

## 9단계: precompute / offline 작업

offline으로 밀어야 할 것:

1. `combined_suppression_mask`
2. `mesh_lite_v2` geometry
3. `hair_luma`
4. render cost bucket
5. per-asset preferred renderer hint

이유:

- runtime에서 매번 계산하거나 파일을 여러 개 읽는 구조를 줄이기 위해서다.

## 우선순위별 실행 순서

### A. 가장 먼저

1. `processing_total_ms` 분리
2. `0009 suppression 제거`
3. `0009 stronger hold`
4. `0009 prewarm`

### B. 그 다음

5. `0009 affine_fast_v1` 도입
6. `0010 combined_suppression_mask`
7. `0010 stronger hold`
8. `0010 stale-state epoch guard`

### C. 구조 변경

9. `0010 mesh_lite_v2`
10. `0010 high-cost asset affine_fast fallback`
11. offline precompute 체계화

## 80ms 목표 관점 최종 판단

### 0009

가장 현실적인 경로:

- suppression 제거
- hold 강화
- 필요 시 `affine_fast_v1`

판단:

- `80ms` 근처 도달 가능성이 높다.

### 0010

가장 현실적인 경로:

- combined suppression mask
- mesh_lite_v2
- high-cost asset에만 affine_fast fallback
- stale-state / fallback 제거

판단:

- 단순 파라미터 조정만으로는 부족하다.
- renderer 구조 변경이 필요하다.

## 핵심 결론

1. 현재 병목은 MediaPipe가 아니라 `overlay`
2. 그 안에서도 가장 큰 비용은 `triangle warp`와 `suppression mask warp`
3. `alpha gain`은 성능 우선순위가 낮다
4. `0009`는 aggressive simplification이 가능하다
5. `0010`은 suppression 1-mask화 + mesh_lite renderer가 필요하다
6. 기존 `mesh_v1`은 싼 경로가 아니므로 대안 renderer를 새로 만들어야 한다
7. 80ms 목표는 `0009`는 현실적, `0010`은 구조 변경이 있어야 현실적이다
