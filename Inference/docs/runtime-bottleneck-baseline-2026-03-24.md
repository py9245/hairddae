# 런타임 병목 기준 정리 (2026-03-24)

## 목적

최근 `inference-server` 로그를 기준으로 `0001`, `0004`, `0010` 헤어의 병목 차이를 정리한다.

이번 정리는 `MediaPipe` 구간을 주 원인 분석에서 제외하고, 아래 항목에 집중했다.

- `hair_overlay`
- `attenuation`
- `hair_parse`
- render failure 횟수
- bundle fallback 횟수

## 로그 기준

- 로그 파일: `/tmp/inference-server-2h.log`
- 수집 명령:

```bash
docker logs --since 2h inference-server > /tmp/inference-server-2h.log 2>&1
```

## 데이터셋 구분 기준

- `0001`: `base_pose_bank__`
- `0004`: `shorthair_short_hair_pose_full_final__`
- `0010`: `H_shortperm_0001_pose_bank__`

## 지표 정의

- `steady-state`: `total < 1000ms` 인 구간
- `non_mp`: `total - tracking - segmentation`
- 이번 비교에서 핵심 병목은 사실상 `hair_overlay`

## 한눈에 보기

| 헤어 | 상태 | 핵심 병목 | 특징 |
|---|---|---|---|
| `0001` | 정상 | `hair_overlay` | 실패 없이 안정적 |
| `0004` | 주의 | `hair_overlay` | 가끔 OpenCV render failure 후 fallback |
| `0010` | 문제 큼 | `hair_overlay` + render failure/fallback churn | 실패와 fallback이 반복됨 |

## 핵심 수치

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

- 전반적으로는 정상에 가깝다.
- 다만 한 번 OpenCV render failure가 나면서 fallback으로 내려간 구간이 있다.
- 그 순간만 `degraded_ok`가 되었고, 이후 다시 `ok`로 회복된다.
- 즉, `0004`는 "대체로 괜찮지만, 특정 렌더 경로가 약하다" 쪽이다.

대표 로그:

- 실패/폴백 구간:
  - [/tmp/inference-server-2h.log:1814](/tmp/inference-server-2h.log:1814)
  - [/tmp/inference-server-2h.log:1816](/tmp/inference-server-2h.log:1816)
  - [/tmp/inference-server-2h.log:1818](/tmp/inference-server-2h.log:1818)
  - [/tmp/inference-server-2h.log:1820](/tmp/inference-server-2h.log:1820)
- 회복 후 정상 구간:
  - [/tmp/inference-server-2h.log:1841](/tmp/inference-server-2h.log:1841)
  - [/tmp/inference-server-2h.log:1851](/tmp/inference-server-2h.log:1851)

### 3. `0010`

- 세 헤어 중 가장 문제가 크다.
- MediaPipe가 아니라 렌더 경로가 주 원인이다.
- OpenCV render failure가 반복적으로 발생한다.
- 그 뒤 bundle fallback이 계속 붙으면서 `hair_overlay` 시간이 크게 튄다.
- 그래서 `0010`은 같은 overlay 구간이어도 `0001`, `0004`보다 훨씬 무겁게 보인다.

대표 로그:

- 실패 반복:
  - [/tmp/inference-server-2h.log:2147](/tmp/inference-server-2h.log:2147)
  - [/tmp/inference-server-2h.log:2156](/tmp/inference-server-2h.log:2156)
  - [/tmp/inference-server-2h.log:2221](/tmp/inference-server-2h.log:2221)
  - [/tmp/inference-server-2h.log:2295](/tmp/inference-server-2h.log:2295)
- fallback 중심 degraded 구간:
  - [/tmp/inference-server-2h.log:2154](/tmp/inference-server-2h.log:2154)
  - [/tmp/inference-server-2h.log:2227](/tmp/inference-server-2h.log:2227)
  - [/tmp/inference-server-2h.log:2301](/tmp/inference-server-2h.log:2301)
  - [/tmp/inference-server-2h.log:2321](/tmp/inference-server-2h.log:2321)
- 안정화되면 다시 정상 수치로 떨어지는 구간:
  - [/tmp/inference-server-2h.log:2338](/tmp/inference-server-2h.log:2338)
  - [/tmp/inference-server-2h.log:2350](/tmp/inference-server-2h.log:2350)

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

1. `0010`의 render failure와 fallback 반복 원인 추적
2. `0004`의 간헐적 render failure 재현 여부 확인
3. `0001`은 정상 baseline으로 유지

## 최종 정리

가장 중요한 한 줄 요약:

`0001`은 정상, `0004`는 간헐적 실패, `0010`은 렌더 실패와 fallback 반복 때문에 overlay가 병목으로 커진 상태다.
