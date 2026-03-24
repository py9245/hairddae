# 런타임 병목 기준 정리 (2026-03-24)

## 목적

최근 `inference-server` 로그를 기준으로 `0001`, `0004`, `0009`, `0010` 헤어의 병목 차이를 정리한다.

이번 정리는 `MediaPipe` 구간을 주 원인 분석에서 제외하고, 아래 항목에 집중했다.

- `hair_overlay`
- `attenuation`
- `hair_parse`
- render failure 횟수
- bundle fallback 횟수

## 빠른 갱신 방법

다음 두 명령으로 로그를 다시 수집하고, 같은 형식의 표를 바로 다시 뽑을 수 있다.

```bash
docker logs --since 20m inference-server > /tmp/inference-recent.log 2>&1
python3 scripts/report_runtime_bottleneck_metrics.py --log-file /tmp/inference-recent.log
```

자동 출력 스크립트:

- [report_runtime_bottleneck_metrics.py](/home/ubuntu/S14P21M101/Inference/scripts/report_runtime_bottleneck_metrics.py)

## 로그 기준

- 기준 로그 1: `/tmp/inference-server-2h.log`
- 수집 명령:

```bash
docker logs --since 2h inference-server > /tmp/inference-server-2h.log 2>&1
```

- 기준 로그 2: `/tmp/inference-recent.log`
- 수집 명령:

```bash
docker logs --since 20m inference-server > /tmp/inference-recent.log 2>&1
```

## 데이터셋 구분 기준

- `0001`: `base_pose_bank__`
- `0004`: `shorthair_short_hair_pose_full_final__`
- `0009`: `base_pose_bank_H_bundlehair_0001__`
- `0010`: `H_shortperm_0001_pose_bank__`

## 지표 정의

- `steady-state`: `total < 1000ms` 인 구간
- `non_mp`: `total - tracking - segmentation`
- 이번 비교에서 핵심 병목은 사실상 `hair_overlay`
- `p95`: nearest-rank 방식

## 최신 스냅샷

- 로그 파일: `/tmp/inference-recent.log`
- 기준 시점: `missing rgb 복구 + lightweight overlay 경량화 + 서버 재시작` 이후
- 해석 포인트:
  - `0004`, `0009`는 현재 `overlay_error=0`, `fallback=0`
  - `0010`은 대부분 `ok`지만 특정 자산에서 render failure `3회`, fallback `1회`가 남아 있다
  - `failed to load image_path`, `failed to load alpha_path`는 현재 `0회`

## 한눈에 보기

| 헤어 | 상태 | 핵심 병목 | 특징 |
|---|---|---|---|
| `0001` | 정상 | `hair_overlay` | 가벼운 baseline |
| `0004` | 정상 | `hair_overlay` | RGB 복구 후 안정화 |
| `0009` | 정상 | `hair_overlay` | 최근 테스트 기준 가장 안정적 |
| `0010` | 주의 | `hair_overlay` + 잔여 render failure | 대부분 정상, 일부 예외 남음 |

## 최신 핵심 수치

| 헤어 | perf 샘플 수 | steady total avg / p50 / p95 | steady overlay avg / p50 / p95 | attenuation p50 | parse p50 | render failure | fallback | 상태 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `0001` | 9 | `111.6 / 109.2 / 178.7 ms` | `42.2 / 31.6 / 76.9 ms` | `8.5 ms` | `0.0 ms` | `0` | `0` | `ok: 9` |
| `0004` | 8 | `175.3 / 171.8 / 232.9 ms` | `122.2 / 135.3 / 154.7 ms` | `7.1 ms` | `0.0 ms` | `0` | `0` | `ok: 8` |
| `0009` | 5 | `152.1 / 158.3 / 223.7 ms` | `95.5 / 112.5 / 128.4 ms` | `7.3 ms` | `0.0 ms` | `0` | `0` | `ok: 5` |
| `0010` | 8 | `240.9 / 166.1 / 988.8 ms` | `85.8 / 119.3 / 138.2 ms` | `8.2 ms` | `0.0 ms` | `3` | `1` | `ok: 8` |

## 잔여 이슈 카운트

- `overlay_error`: `0`
- `failed to load image_path`: `0`
- `failed to load alpha_path`: `0`
- `bundle_render_fallback`: `1`
- `matrix_iterator.cpp` OpenCV assert: `3`
- `rtc asset bundle build failed`: `3`

## 히스토리 기준선

아래 표는 이전 2시간 로그 기준의 초기 baseline이다. 최근 개선 전 수치와 비교할 때 참고한다.

| 헤어 | perf 샘플 수 | steady total avg / p50 / p95 | steady overlay avg / p50 / p95 | attenuation p50 | parse p50 | render failure | fallback | 상태 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `0001` | 25 | `229.3 / 214.8 / 362.9 ms` | `122.9 / 93.0 / 249.4 ms` | `14.9 ms` | `0.0 ms` | `0` | `0` | `ok: 25` |
| `0004` | 6 | `323.7 / 270.5 / 738.2 ms` | `202.8 / 151.7 / 557.7 ms` | `19.5 ms` | `0.0 ms` | `2` | `1` | `ok: 5`, `degraded_ok: 1` |
| `0010` | 15 | `538.4 / 589.5 / 872.3 ms` | `395.6 / 470.1 / 607.9 ms` | `21.2 ms` | `0.0 ms` | `65` | `31` | `degraded_ok: 12`, `ok: 3` |

## 결론 요약

### 1. `0001`

- 현재 기준에서 가장 건강한 기준선이다.
- `hair_overlay`가 가장 큰 비용이긴 하지만, 전체적으로 안정적이다.
- render failure와 fallback이 없다.
- 즉, `0001`은 "현재 정상 baseline"으로 봐도 된다.

대표 로그:

- [/tmp/inference-server-2h.log:2017](/tmp/inference-server-2h.log:2017)
- [/tmp/inference-server-2h.log:2025](/tmp/inference-server-2h.log:2025)
- [/tmp/inference-server-2h.log:2033](/tmp/inference-server-2h.log:2033)

### 2. `0004`

- `image_path` 누락 복구 이후 최근 로그에서는 render failure와 fallback이 없다.
- 현재는 `mesh_v2` overlay 경로로 정상 동작한다.
- 즉, `0004`는 지금 기준으로는 정상군에 넣어도 된다.

대표 로그:

- 최근 정상 구간:
  - [/tmp/inference-recent.log](/tmp/inference-recent.log)

### 3. `0009`

- 최근 테스트에서 정상 적용이 확인됐다.
- 현재 steady 기준 `0004`보다 약간 가볍고, fallback도 없다.
- 즉, `0009`는 현재 기준 안정권이다.

대표 로그:

- 최근 정상 구간:
  - [/tmp/inference-recent.log](/tmp/inference-recent.log)

### 4. `0010`

- 이전 baseline에 비하면 크게 개선됐다.
- 최근 steady 기준 `ok`로 지나가는 프레임이 대부분이다.
- 다만 특정 자산에서 OpenCV assert `3회`, fallback `1회`가 남아 있다.
- 즉, `0010`은 "대부분 정상이나 잔여 예외가 남은 상태"로 보는 게 맞다.

대표 로그:

- 최근 정상 구간:
  - [/tmp/inference-recent.log](/tmp/inference-recent.log)
- 잔여 예외 구간:
  - `H_shortperm_0001_pose_bank__yaw+16_pitch-06_roll+00_frame009948`
  - `H_shortperm_0001_pose_bank__yaw+15_pitch-05_roll+00_frame009946`

## 무엇이 병목이 아니었나

### `attenuation`

병목의 주범은 아니다.

- `0001`: `14.9ms`
- `0004`: `19.5ms`
- `0010`: `21.2ms`

즉, 셋 다 attenuation 차이만으로 전체 성능 차이를 설명하기는 어렵다.

### `hair_parse`

지속 병목은 아니다.

- 대부분의 로그는 `hair_parse=0.0ms`
- 일부 초기 balanced 프레임에서만 튄다
- `0001`의 큰 값도 warmup 성격이 강하다

즉, 지금 눈에 띄는 차이는 `hair_parse`보다 `render 안정성`이다.

## 실무 기준 우선순위

현재 로그만 기준으로 잡으면 우선순위는 이렇다.

1. `0010`의 잔여 OpenCV assert 1건 계열 추적
2. `select_hair` 전환 시 다른 데이터셋 `asset_id`가 섞이는 경고 정리
3. `0001`, `0004`, `0009`는 정상 baseline으로 유지

## 최종 정리

가장 중요한 한 줄 요약:

`0001`, `0004`, `0009`는 현재 정상권이고, `0010`도 대부분 정상으로 회복됐다. 지금 남은 핵심 과제는 `0010`의 잔여 render failure와 전환 순간 asset id mismatch 경고다.
