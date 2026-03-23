# RTC Optimization Log

## 문서 목적

이 문서는 Inference 서버의 RTC 성능을 단계적으로 개선하면서, 각 단계에서 무엇을 바꿨고 어떤 효과가 있었는지를 기록하기 위한 문서입니다.

비전공자 기준으로 보면, 이번 최적화는 아래 질문에 답하기 위한 작업입니다.

- 사용자가 사이트에 들어와 카메라를 켰을 때, 왜 처음 연결이 느린가?
- 머리 스타일을 처음 적용할 때, 왜 첫 화면이 늦게 붙는가?
- 느린 원인이 네트워크인지, 서버 처리인지 어떻게 구분할 수 있는가?

각 단계는 아래 형식으로 정리합니다.

- 목적: 이 단계를 왜 했는가
- 방법: 서버에서 무엇을 바꿨는가
- 결과: 실제 테스트 후 숫자가 어떻게 달라졌는가
- 해석: 그래서 다음에 어디를 더 봐야 하는가

## Metrics

- `offer_200_ms`: `rtc offer accepted`부터 `POST /rtc/offer 200 OK`까지
- `data_channel_ms`: `rtc offer accepted`부터 `rtc data channel opened`까지
- `first_feature_ms`: `rtc offer accepted`부터 `rtc server feature: seq=1`까지
- `first_frame_total_ms`: 첫 `rtc pipeline timing: frames=1`의 `avg_total_ms`
- `first_frame_tracking_ms`: 첫 `rtc pipeline timing: frames=1`의 `tracking_ms`
- `first_frame_selection_ms`: 첫 `rtc pipeline timing: frames=1`의 `selection_ms`
- `first_frame_compose_ms`: 첫 `rtc pipeline timing: frames=1`의 `compose_ms`
- `transport_ms`: 프레임이 RTC source track에 도착한 뒤 실제 처리 결과가 나갈 때까지의 샘플 지연
- `transport_avg_ms`: 세션 동안 누적 평균 transport 지연
- `transport_max_ms`: 세션 동안 관측된 최대 transport 지연

## 초기 연결 시간이란?

이 문서에서 말하는 `초기 연결 시간`은, 사용자가 사이트에서 카메라 사용을 시작한 뒤 Inference 서버와 RTC 연결이 실제로 준비될 때까지 걸리는 초반 구간을 뜻합니다.

쉽게 말하면 아래 순서입니다.

1. 사용자가 페이지에 들어와 카메라 권한을 허용함
2. 브라우저가 Inference 서버에 "연결을 시작하자"는 요청을 보냄
3. 서버가 연결에 필요한 정보를 계산해서 응답함
4. 브라우저와 서버가 서로 연결을 실제로 붙임
5. 첫 카메라 프레임이 서버에서 처리되기 시작함

사용자 입장에서는 이 시간이 길수록 아래처럼 느껴집니다.

- 카메라는 켜졌는데 실제 반응이 늦다
- 첫 화면이 붙기까지 멈춘 것처럼 보인다
- 머리 스타일을 선택해도 바로 적용되지 않는 것처럼 느껴진다

이 문서에서는 이 초반 구간을 한 번에 뭉뚱그리지 않고 세 단계로 나눠서 봅니다.

- `offer_200_ms`
  - 브라우저가 서버에 연결 시작 요청을 보낸 뒤, 서버가 첫 응답을 돌려줄 때까지의 시간입니다.
  - 쉽게 말하면 "서버가 연결 준비를 시작해서 답장을 주는 데 걸린 시간"입니다.
- `data_channel_ms`
  - 서버 응답 이후 실제 RTC 연결이 더 진행되어, 브라우저와 서버 사이의 데이터 통로가 열릴 때까지의 시간입니다.
  - 쉽게 말하면 "연결이 서류상으로만 아니라 실제로 붙기 시작한 시간"입니다.
- `first_feature_ms`
  - 연결이 붙은 뒤, 서버가 첫 카메라 프레임을 받아 실제 처리 결과를 만들기 시작할 때까지의 시간입니다.
  - 쉽게 말하면 "연결만 된 상태"에서 끝나는 것이 아니라, "실제로 첫 화면 처리가 시작된 시점"까지 포함한 시간입니다.

정리하면, `초기 연결 시간`은 단순히 버튼을 누른 뒤 서버가 응답하는 한 구간만 뜻하는 것이 아니라, 사용자가 실제로 "연결이 됐다"고 체감하기 전까지의 초반 준비 과정을 뜻합니다.

그래서 이번 최적화도 아래처럼 나눠서 보는 것이 중요합니다.

- `offer_200_ms`가 느리면: 연결 시작 준비가 느린 문제
- `data_channel_ms`가 느리면: RTC 연결이 실제로 붙는 과정이 느린 문제
- `first_feature_ms`가 느리면: 연결은 됐지만 첫 화면 처리 준비가 느린 문제

## Step 1

- Date: `2026-03-23`
- Branch: `feat/RTC_upgrade_v2`
- Change:
  - `INFERENCE_RTC_WAIT_FOR_ICE_GATHERING`
  - `INFERENCE_RTC_ICE_GATHERING_TIMEOUT_MS`
  - `INFERENCE_RTC_AIOICE_GATHER_TIMEOUT_MS`
  - `aioice` gather timeout patch 반영
- Goal:
  - `offer` 병목 제거
  - ICE candidate gather 대기 시간을 설정값대로 제한

### 쉬운 설명

- 목적:
  - 사용자가 사이트에 접속했을 때 "연결을 시작하는 첫 단계"가 너무 오래 걸리는 문제를 줄이기 위한 작업입니다.
  - 이전 기록상 이 구간은 약 `5초` 정도 걸린 적이 있어서, 사용자는 "카메라가 늦게 켜진다" 또는 "연결이 느리다"고 느낄 수 있었습니다.
- 방법:
  - Inference 서버가 WebRTC 연결을 만들 때, 네트워크 후보를 모으느라 오래 기다리지 않도록 제한 시간을 더 짧고 명확하게 잡았습니다.
  - 쉽게 말하면, "연결 후보를 찾는 시간"을 오래 끌지 않도록 서버 설정을 조정했습니다.
- 기대 효과:
  - 연결 시작 단계가 빨라져서, 사용자가 카메라를 켠 뒤 첫 응답을 더 빨리 받게 만드는 것입니다.

### Historical Before

- Prior optimization note baseline: `offer ~= 5.03s`

### After

| Run | offer_200_ms | data_channel_ms | first_feature_ms | first_frame_total_ms | first_frame_tracking_ms | first_frame_selection_ms | first_frame_compose_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 417.2 | 913.1 | 1172.9 | 652.2 | 110.1 | 102.9 | 382.3 |
| 2 | 336.6 | 765.5 | 963.3 | 213.2 | 90.5 | 70.2 | 6.4 |
| 3 | 265.5 | 722.1 | 895.5 | 351.4 | 135.1 | 6.8 | 163.7 |

### Summary

- `offer_200_ms`: `5.03s -> 0.27s ~ 0.42s`
- Current remaining bottleneck:
  - `offer`보다는 `seq=1` 첫 프레임 warm-up
  - 특히 `tracking`, `selection`, `compose`가 세션별로 크게 튐

### 비전공자용 결과 해석

- 결과:
  - 가장 먼저 줄이고 싶었던 "초기 연결 시작 시간"은 확실히 좋아졌습니다.
  - 과거에는 약 `5초` 정도 걸리던 구간이, 이번 테스트에서는 대략 `0.27초 ~ 0.42초` 수준까지 줄었습니다.
- 의미:
  - 즉, "처음 연결을 시작하는 단계"는 이제 큰 병목이 아닙니다.
  - 사용자가 여전히 느리다고 느낀다면, 원인은 이제 연결 시작이 아니라 "첫 화면을 실제로 만들어 보여주는 과정" 쪽일 가능성이 큽니다.
- 다음 판단:
  - 그래서 다음 단계에서는 네트워크보다, 첫 프레임을 만드는 서버 내부 처리 시간을 더 자세히 보기로 했습니다.

## Step 2

- Date: `2026-03-23`
- Branch: `feat/RTC_upgrade_v2`
- Change:
  - `RtcTransportStats` 추가
  - `rtc pipeline timing`에 `transport_ms`, `transport_avg_ms`, `transport_max_ms`, `transport_count` 추가
  - connection close 시 `rtc transport summary` 추가
- Goal:
  - `wait_frame_ms` / `avg_server_ms` 외에 수신 이후 지연을 분리
  - 네트워크/수신 버퍼와 서버 처리 지연을 구분해서 다음 최적화 방향 결정

### 쉬운 설명

- 목적:
  - 사용자가 느끼는 지연이 "인터넷이나 RTC 전송 때문인지", 아니면 "서버가 첫 화면을 만드는 데 오래 걸려서인지"를 구분하기 위한 단계입니다.
- 방법:
  - 서버 로그에 transport 관련 시간을 추가로 남기도록 했습니다.
  - 쉽게 말하면, "카메라 프레임이 서버에 들어온 뒤 실제 결과가 나갈 때까지"의 시간을 따로 기록하게 만들었습니다.
  - 이 기록으로 네트워크 구간과 서버 처리 구간을 나눠서 볼 수 있게 했습니다.
- 기대 효과:
  - 다음 최적화에서 엉뚱한 부분을 건드리지 않고, 진짜 느린 부분만 정확히 잡을 수 있습니다.

### After

| Run | offer_200_ms | data_channel_ms | first_feature_ms | transport_ms | transport_avg_ms | transport_max_ms | first_frame_total_ms | avg_server_ms | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 569.0 | 1016.0 | 1312.9 | 512.6 | 28.3 | 127.2 | 588.7 | 512.2 | First frame server spike remained large; compose 276.7ms |
| 2 | 292.2 | 765.7 | 1002.1 | 118.7 | 31.7 | 64.7 | 277.3 | 118.4 | Offer path stable; first frame much lower than run 1 |
| 3 | 207.7 | 611.8 | 806.9 | 132.8 | 28.3 | 54.1 | 207.9 | 132.6 | Offer path fastest; selection 58.8ms remained visible |

### Summary

- `offer_200_ms` remained stable at `0.21s ~ 0.57s`
- `transport_avg_ms` settled around `28ms ~ 32ms`
- `transport_max_ms` stayed within `54ms ~ 127ms`
- Current remaining bottleneck:
  - average transport delay is not the main issue
  - first-frame server warm-up is still dominant
  - major spikes are still in `avg_server_ms`, especially `tracking`, `selection`, and `compose`

### 비전공자용 결과 해석

- 결과:
  - 네트워크 전송 구간의 평균 지연은 대략 `28ms ~ 32ms` 수준이었습니다.
  - 반면 첫 화면을 만들 때 서버 처리 시간은 회차에 따라 `118ms`, `132ms`, 심하면 `512ms`까지 크게 튀었습니다.
- 의미:
  - 즉, 지금 사용자가 느끼는 "버벅임"이나 "처음 붙는 속도 저하"의 주된 원인은 네트워크가 아니라 서버의 첫 프레임 처리입니다.
  - 특히 얼굴 추적(`tracking`), 어떤 헤어를 고를지 판단하는 과정(`selection`), 실제로 합성하는 과정(`compose`)이 첫 프레임에서 크게 튀고 있습니다.
- 결론:
  - 이번 단계는 직접 속도를 높인 단계라기보다, 느린 원인이 어디인지 분리해 낸 단계입니다.
  - 이 결과를 바탕으로 다음 단계는 `first-frame warm-up` 최적화로 가는 것이 맞습니다.

## 현재까지 한 줄 요약

- 1단계에서 "연결 시작 지연"은 크게 줄였습니다.
- 2단계에서 "남은 병목은 네트워크보다 첫 프레임 서버 처리"라는 점을 확인했습니다.
- 다음 작업은 첫 프레임에서 필요한 준비 작업을 미리 당겨서, 사용자가 처음 헤어를 적용할 때 느끼는 버벅임을 줄이는 것입니다.
