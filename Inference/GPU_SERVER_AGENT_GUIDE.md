# Inference GPU Server Agent Guide

## 1. 이 문서의 목적

이 문서는 새로 합류한 인프런스 서버 담당자, 운영자, 또는 AI 에이전트가 이 저장소를 빠르게 이해하고 바로 작업할 수 있도록 만든 기준 문서다.

이 문서가 답하려는 질문은 아래와 같다.

- 이 서비스는 사용자에게 무엇을 제공하는가
- 현재 `FE / BE / Inference / static`은 어떻게 연결되어 있는가
- 현재 Git에 어떤 것이 들어 있고, 무엇이 배포 산출물인가
- 인프런스 서버는 왜 별도 GPU 서버로 분리하려고 하는가
- 현재 병목은 어디이며, 어떤 순서로 개선해야 하는가
- GPU 서버를 고른다면 어떤 사양이 현실적인가
- 새 담당자가 어느 파일부터 읽고 어디를 수정해야 하는가

이 문서는 "설명용 개요"가 아니라 "실제 인수인계용 운영 문서"를 목표로 한다.

---

## 2. 서비스 한 줄 설명

이 서비스는 사용자의 실시간 카메라 화면에 선택한 헤어스타일을 자연스럽게 합성해 보여주는 서비스다.

현재 구조는 크게 두 단계로 나뉜다.

1. `BE`가 실시간 세션을 열고 짧은 수명의 접속 티켓을 발급한다.
2. `FE`가 얼굴 landmark/pose를 추출해서 `Inference`에 보내고, `Inference`는 가장 잘 맞는 헤어 asset과 렌더 정보를 계산한다.

초기 구현은 `FE에서 직접 오버레이를 그리는 구조`였고, 지금은 `RTC + 서버 렌더` 경로를 붙이는 중이다.

즉, 이 저장소는 단순한 API 서버가 아니라 아래를 모두 포함한다.

- 프론트 카메라 처리
- 세션 발급 백엔드
- 실시간 인프런스 서버
- 정적 헤어 asset 데이터셋
- nginx / docker compose 기반 배포 설정

---

## 3. 저장소 전체 구조

루트 기준 핵심 디렉터리는 아래와 같다.

### `FE/`

브라우저 카메라, MediaPipe landmark 추출, 실시간 세션 연결, 화면 표시를 담당한다.

중요 파일:

- `FE/src/components/Camera/FaceLandmarksView.tsx`
- `FE/src/hooks/Camera/useHairInferenceSession.ts`
- `FE/src/hooks/Camera/useHairRtcSession.ts`
- `FE/src/hooks/Camera/useFaceLandmarkersLoop.ts`
- `FE/src/hooks/Camera/useFaceTrackingLoop.ts`
- `FE/src/lib/Camera/inference.ts`
- `FE/src/lib/Camera/overlay.ts`
- `FE/src/lib/Camera/runtime.ts`

### `BE/`

Spring Boot API 서버다. 세션 시작, resume, 접속 티켓 발급, 정적 asset bootstrap 정보를 내려준다.

중요 파일:

- `BE/src/main/java/com/example/beapp/service/HomeService.java`
- `BE/src/main/java/com/example/beapp/api/dto/home/HairApplyV2Response.java`
- `BE/src/main/java/com/example/beapp/config/AppInferenceProperties.java`
- `BE/docker-compose.yml`
- `BE/docker-compose.local.yml`
- `BE/nginx/default.conf`
- `BE/nginx/local.conf`

### `Inference/`

Python FastAPI/ASGI 기반 실시간 인프런스 서비스다. 현재는 WebSocket feature 처리와 RTC offer/answer, 서버 렌더 경로를 모두 담고 있다.

중요 파일:

- `Inference/app/main.py`
- `Inference/app/rtc.py`
- `Inference/app/catalog.py`
- `Inference/app/render.py`
- `Inference/app/server_render.py`
- `Inference/app/auth.py`
- `Inference/app/config.py`

### `static/`

헤어 데이터셋이 들어 있다. 현재 예시는 `static/0001`이다.

중요 하위 구조:

- `static/0001/manifests/asset_index_v0.json`
- `static/0001/metadata/*.json`
- `static/0001/anchors/*.json`
- `static/0001/hair_rgba/*.png`
- `static/0001/masks/...`

### `BE/nginx/html/`

로컬 및 서버 nginx가 서빙하는 프론트 정적 산출물 위치다.

주의:

- 이 디렉터리는 소스 코드가 아니다.
- `FE/dist`를 빌드한 뒤 복사해 넣는 배포 산출물이다.
- FE 변경의 기준은 항상 `FE/src/**`다.

---

## 4. 사용자 입장에서의 서비스 흐름

사용자는 대략 아래 순서로 이 기능을 경험한다.

1. `https://.../camera`에 접속한다.
2. 브라우저가 카메라를 연다.
3. 사용자가 헤어를 선택한다.
4. FE가 `BE`에 실시간 apply 세션 시작 요청을 보낸다.
5. `BE`는 `apply_session_id`, connect ticket, inference 연결 정보, static preload 정보를 내려준다.
6. FE는 선택된 전송 방식에 따라 `Inference`와 연결한다.
   - 기존: WebSocket
   - 현재 추가 중: RTC
7. FE는 landmark/pose 기반 feature를 주기적으로 보낸다.
8. `Inference`는 가장 맞는 asset을 고르고 render task를 계산한다.
9. 화면에는 헤어가 실시간으로 보인다.

핵심은 `Inference`가 사용자의 원본 얼굴 정보를 모두 직접 처리하는 게 아니라, 현재 구조에서는 `FE가 feature를 먼저 만든다`는 점이다.

---

## 5. 현재 아키텍처를 한 문장씩 설명하면

### FE의 역할

- 카메라를 연다.
- MediaPipe로 얼굴 landmark를 찾는다.
- pose와 anchor를 계산한다.
- feature 메시지를 만든다.
- `BE`에서 받은 bootstrap 정보를 이용해 `Inference`와 연결한다.
- 기존 구조에선 브라우저가 직접 PNG를 그렸다.
- 현재 RTC 경로에서는 서버가 렌더한 비디오를 받는다.

### BE의 역할

- 사용자의 인증을 처리한다.
- 헤어 적용 세션을 만든다.
- `apply_session_id`를 만든다.
- `Inference` 접속용 short-lived ticket을 발급한다.
- WS URL, RTC offer URL, ICE 서버 정보, static preload 정보를 묶어서 FE에 내려준다.

### Inference의 역할

- connect ticket을 검증한다.
- feature를 받아 가장 적합한 헤어 asset을 선택한다.
- hysteresis와 hold 로직으로 asset이 너무 자주 흔들리지 않게 한다.
- WebSocket에서는 asset bundle만 돌려준다.
- RTC에서는 원격 비디오 트랙을 받아 서버에서 렌더 후 다시 비디오 트랙으로 보낸다.

### static의 역할

- 헤어 PNG, anchor, metadata, mask, manifest를 제공한다.
- 이 데이터는 FE preload에도 쓰이고, Inference 추천/렌더 계산에도 쓰인다.

---

## 6. 현재 실시간 세션 시작 흐름

실제 기준 파일은 [`HomeService.java`](/home/yusin/S14P21M101/BE/src/main/java/com/example/beapp/service/HomeService.java) 이다.

### 6.1 세션 시작

FE는 아래 API를 호출한다.

- `POST /home/hairapplybootstrap`
- `POST /home/hairapplyresume`

`HomeService.startHairApplyV2()`와 `resumeHairApplyV2()`가 이를 처리한다.

### 6.2 BE가 내려주는 정보

응답 DTO는 [`HairApplyV2Response.java`](/home/yusin/S14P21M101/BE/src/main/java/com/example/beapp/api/dto/home/HairApplyV2Response.java) 이다.

응답에는 크게 3개가 들어 있다.

- `inference`
  - WebSocket 주소
  - connect ticket
  - timeout 정보
- `rtc`
  - RTC offer URL
  - connect ticket
  - ICE 서버 목록
- `static`
  - dataset base URL
  - asset index URL
  - preload 대상 asset id 목록

즉, FE는 이 한 번의 bootstrap 응답만으로 실시간 연결에 필요한 거의 모든 것을 얻는다.

---

## 7. 현재 두 가지 실시간 경로

## 7.1 기존 WebSocket feature-only 경로

관련 파일:

- `Inference/app/main.py`
- `FE/src/hooks/Camera/useHairInferenceSession.ts`

흐름:

1. FE가 landmark/pose에서 feature를 만든다.
2. FE가 WebSocket으로 feature JSON을 보낸다.
3. Inference가 추천 asset을 고른다.
4. Inference가 `processed` 메시지로 asset bundle을 돌려준다.
5. FE가 PNG/anchors를 읽고 캔버스에 직접 그린다.

장점:

- 네트워크로 전체 프레임을 보내지 않는다.
- Inference 부하가 비교적 가볍다.
- FE에서 local render가 가능하다.

단점:

- 자연스러운 합성 로직이 브라우저 쪽으로 복잡해진다.
- 기존 머리 제거, 얼굴 보호 마스크, 다중 레이어 합성 등을 넣기 어려워진다.
- 모바일/브라우저 편차를 크게 탄다.

## 7.2 현재 추가 중인 RTC + 서버 렌더 경로

관련 파일:

- `Inference/app/rtc.py`
- `Inference/app/server_render.py`
- `FE/src/hooks/Camera/useHairRtcSession.ts`

흐름:

1. FE가 로컬 카메라 비디오 트랙을 `RTCPeerConnection`으로 보낸다.
2. FE는 feature는 data channel로 별도 전송한다.
3. Inference는 비디오 트랙과 feature를 동시에 받는다.
4. Inference는 최신 선택 asset 기준으로 서버에서 합성한다.
5. Inference는 렌더된 비디오를 RTC remote track으로 다시 보낸다.
6. FE는 remote video를 화면에 표시한다.

장점:

- 최종 합성 품질을 서버에서 통제할 수 있다.
- FE draw 병목이 줄어든다.
- 앞으로 세그멘테이션, 마스크, 자연화 작업을 서버에 몰아넣기 좋다.

단점:

- 비디오 프레임과 feature를 동기화해야 한다.
- TURN/ICE/networking 운영 난이도가 올라간다.
- 서버가 video decode/encode/render를 같이 감당해야 한다.

---

## 8. 현재 RTC 경로에서 발생하는 핵심 문제

최근 관찰한 현재 증상:

- RTC offer는 정상적으로 `200`이 나온다.
- 내 얼굴은 보인다.
- 헤어가 처음엔 이상한 절대 위치에 뜬다.
- 잠시 뒤 머리에 안착한다.
- 전체 체감 속도가 아주 빠르지는 않다.

이 문제의 핵심 원인은 "렌더 수학이 완전히 틀렸다"라기보다 "동기화와 전송 정책"에 있다.

### 8.1 원격 화면 전환이 너무 이르다

관련 파일:

- `FE/src/components/Camera/FaceLandmarksView.tsx`

현재는 remote video가 재생 가능해지는 순간 원격 화면을 보여준다.
하지만 이 시점에는 첫 안정된 `processed` 결과가 아직 없을 수 있다.

즉:

- 비디오는 먼저 오고
- 헤어 위치 정보는 뒤늦게 안정화된다

그래서 사용자는 처음 몇 프레임 동안 "그냥 내 얼굴" 또는 "이상 위치의 헤어"를 보게 된다.

### 8.2 feature와 비디오 프레임이 시간적으로 묶여 있지 않다

관련 파일:

- `Inference/app/rtc.py`
- `FE/src/lib/Camera/inference.ts`

FE는 feature에 `seq`와 `ts_ms`를 넣어 보낸다.
하지만 현재 서버 렌더는 `현재 도착한 비디오 프레임`에 `가장 최근에 처리된 bundle`을 그대로 얹는다.

즉, 현재 구조는 아래와 같다.

- frame A 수신
- feature X 처리
- frame B 수신
- feature Y 처리
- 렌더는 "해당 frame과 정확히 맞는 feature"가 아니라 "그 순간 최신 feature 결과"를 사용

이 구조는 머리 움직임이 있으면 초기에 위치가 튀기 쉽다.

### 8.3 FE feature 송신이 single in-flight 성격을 가진다

관련 파일:

- `FE/src/hooks/Camera/useHairRtcSession.ts`

이전 구현은 한 번에 하나의 feature만 보내고, 처리 중이면 최신 1개만 pending으로 덮어썼다.

이 정책은 장점도 있다.

- 서버 큐 폭주를 막는다.
- 오래된 feature가 많이 쌓이지 않는다.

하지만 단점도 분명하다.

- 비디오 프레임은 20fps 이상으로 흐르는데
- 실제 헤어 위치 갱신은 RTT에 묶인다

결과적으로 "한동안 헤어가 늦게 따라오다가 갑자기 맞는 위치로 붙는" 체감이 생긴다.

### 8.4 현재 서버 렌더는 아직 GPU 경로가 아니다

관련 파일:

- `Inference/app/server_render.py`
- `Inference/app/rtc.py`

현재 서버 렌더는 대략 아래 순서다.

1. `frame.to_image()`
2. Pillow `Image.transform(...)`
3. `Image.alpha_composite(...)`
4. `VideoFrame.from_image(...)`

즉, 현재는 CPU + Pillow 중심 경로다.

GPU 서버를 붙여도 이 코드가 그대로면 "GPU가 있는데 CPU처럼 느린" 상황이 될 수 있다.

---

## 9. 현재 병목 정리

최근 로컬 컨테이너 기준 측정값은 대략 아래와 같았다.

- `catalog.recommend`: 약 `1.5ms`
- `RTC recv pipeline`
  - `frame.to_image`
  - `compose_bundle_frame`
  - `VideoFrame.from_image`
  - 합산 약 `4.1ms`

이 숫자가 말하는 핵심은 다음이다.

### 지금 1순위 병목

- 추천 로직 그 자체는 이미 가장 큰 병목이 아니다.
- 순수 단일 프레임 합성 연산도 현재는 절대적으로 터무니없이 느린 수준은 아니다.
- 지금 체감 병목은 아래가 더 크다.

1. FE landmark 추출 주기
2. data channel 왕복 지연
3. in-flight 정책
4. video frame과 feature 결과의 비동기화
5. TURN relay 사용 시 추가 RTT

즉, "느리다"의 핵심은 계산량보다 파이프라인의 결합 방식에 더 가깝다.

### 앞으로 1순위 병목이 될 것

아래가 추가되면 병목은 GPU/서버 렌더로 옮겨간다.

- 기존 머리 제거
- 얼굴 보호 마스크
- 이마/귀/목 처리
- 다중 레이어 합성
- temporal smoothing
- 비디오 인코딩 최적화

즉, 지금은 "GPU가 없어도 어느 정도는 돈다"가 맞지만, 앞으로는 "GPU가 없으면 자연스러운 품질을 감당하기 어렵다"가 맞다.

---

## 10. 현재 Git으로 관리되는 것과 아닌 것

새 담당자가 가장 많이 헷갈리는 부분이라 분리해서 적는다.

## 10.1 Git으로 관리되는 것

- FE 소스 코드
- BE 소스 코드
- Inference 소스 코드
- docker compose 파일
- nginx 설정
- 정적 데이터셋 `static/0001`
- 문서

즉, 서비스 논리와 정적 asset 원본은 기본적으로 Git 안에 있다.

## 10.2 Git에 있지만 "배포 산출물" 성격인 것

- `FE/dist`
- `BE/nginx/html`

주의:

- 이 둘은 사람이 직접 수정하는 기준 파일이 아니다.
- `FE/src/**`를 수정한 뒤 `pnpm build` 결과로 다시 생성된다.
- 로컬 테스트 때는 `BE/nginx/html`이 최신 FE를 서빙하므로 중요하지만, 소스의 진실은 아니다.

## 10.3 Git으로 관리하지 않는 것

- `.env`
- 운영용 비밀키
- 실제 DB 데이터
- Redis 런타임 데이터
- 운영 서버의 인증서

중요:

- `APP_SECURITY_JWT_SECRET`
- `APP_SECURITY_JWT_ISSUER`

이 둘은 `BE`와 `Inference`가 반드시 같아야 한다.
다르면 connect ticket 검증이 실패한다.

---

## 11. 정적 데이터셋을 이해하는 법

현재 데이터셋은 대략 아래 조합으로 동작한다.

### `asset_index_v0.json`

빠른 선택용 index다.

들어 있는 것:

- `asset_id`
- pose 정보
- geometry score용 필드
- approved 여부

추천 로직은 이 index를 먼저 본다.

### `metadata/*.json`

개별 asset에 대한 자세한 정보가 들어 있다.

중요 필드:

- `hair_rgba_path`
- `hair_rgba_bbox`
- `image_size`
- `face_bbox`
- 각종 mask path

### `anchors/*.json`

asset 고유 anchor 좌표가 들어 있다.

이 데이터와 사용자의 현재 feature anchor를 비교해서 `render_task`를 만든다.

### `hair_rgba/*.png`

실제 헤어 이미지다.

중요한 사실:

- 이 PNG는 "전체 프레임"이 아니라 이미 `hair_bbox` 기준으로 crop된 이미지다.

이 점을 이해하지 못하면, 서버 렌더에서 이미지를 한 번 더 잘못 자르는 버그가 다시 생길 수 있다.

---

## 12. 새 담당자가 반드시 알아야 하는 핵심 소스 파일

### 12.1 추천 로직

파일:

- `Inference/app/catalog.py`

역할:

- asset index 로드
- metadata/anchors 캐시
- geometry 계산
- retrieval score 계산
- 추천 asset bundle 생성

중요 포인트:

- 현재 가장 무거웠던 `feature geom` 중복 계산은 이미 줄여둔 상태다.
- 추천 자체는 현재 매우 빠른 편이다.

### 12.2 render_task 생성

파일:

- `Inference/app/render.py`

역할:

- 사용자 anchor와 asset anchor를 이용해 affine/similarity transform 계산
- destination ROI 계산
- FE 또는 서버 렌더가 사용할 render task 생성

여기는 FE/Inference 좌표계 계약의 중심이다.

### 12.3 RTC 서버 렌더

파일:

- `Inference/app/rtc.py`
- `Inference/app/server_render.py`

역할:

- RTC offer/answer 처리
- video track 수신
- data channel 수신
- 최신 bundle로 비디오 프레임 렌더

중요 포인트:

- 현재는 frame timestamp와 feature timestamp의 정밀 매칭이 없다.
- 따라서 앞으로 quality를 올리려면 여기부터 손대야 한다.

### 12.4 FE RTC 세션

파일:

- `FE/src/hooks/Camera/useHairRtcSession.ts`

역할:

- bootstrap 받기
- RTCPeerConnection 만들기
- local video track 보내기
- data channel로 feature 보내기
- remote video track 받기
- HUD metric 업데이트

여기는 네트워크 체감 품질을 좌우한다.

### 12.5 BE bootstrap

파일:

- `BE/src/main/java/com/example/beapp/service/HomeService.java`

역할:

- connect ticket 발급
- RTC/WS/static bootstrap 통합 응답 구성
- preload asset id 선정

인프런스 서버를 별도 GPU 서버로 분리할 때도, 대개 이 파일의 contract는 유지하는 편이 좋다.

---

## 13. 왜 인프런스를 별도 GPU 서버로 분리하려는가

이유는 크게 세 가지다.

### 13.1 역할이 달라진다

처음엔 Inference가 "가벼운 추천 서버"였다.
하지만 앞으로는 아래를 담당할 가능성이 높다.

- 기존 머리 제거
- 마스크 조합
- 자연스러운 경계 처리
- 최종 합성
- 비디오 인코딩

이 단계부터는 단순 API 서버와 성격이 완전히 다르다.

### 13.2 스케일링 기준이 다르다

BE는 보통 다음이 중요하다.

- 인증
- 짧은 HTTP 요청
- DB/Redis

Inference/Media는 다음이 중요하다.

- 장시간 연결
- CPU/GPU 부하
- 메모리
- 비디오 encode/decode

같은 서버에 묶으면 스케일링이 어려워진다.

### 13.3 장애 분리가 쉬워진다

GPU 렌더가 튀거나 지연이 생겨도, 로그인/API까지 같이 흔들리면 운영이 매우 어려워진다.

따라서 장기적으로는 아래 구조가 맞다.

- `BE/API 서버`
- `Inference/GPU 미디어 서버`
- `Static/CDN 또는 nginx`
- 필요 시 `TURN`

---

## 14. GPU 서버를 고를 때의 기준

이 서비스는 "대형 LLM 추론 서버"와 다르다.

중요한 것은 아래다.

- 한 사용자당 실시간 video track 처리
- mask/segmentation 추론
- 합성
- 가능하면 하드웨어 인코딩
- 여러 세션 동시 처리

즉, "메모리만 매우 큰 GPU"보다 "영상/실시간 추론/전력 효율이 좋은 GPU"가 더 적합하다.

---

## 15. 현재 추천 하드웨어

## 15.1 가장 추천

### `NVIDIA L4` 1장

권장 서버:

- GPU: `L4 24GB`
- CPU: `8~16 vCPU`
- RAM: `32~64GB`
- SSD: `NVMe 200GB+`
- 네트워크: `10Gbps` 이상 권장

이 구성이 좋은 이유:

- 영상/추론 혼합 워크로드에 밸런스가 좋다.
- 전력 대비 효율이 좋다.
- 실서비스 1차 GPU 분리 서버로 과하지도, 너무 약하지도 않다.

추천 상황:

- 첫 번째 운영용 인프런스/미디어 서버
- RTC + 서버 렌더 + 추가 자연화 작업 예정

## 15.2 온프렘/대안

### `NVIDIA A10` 1장

권장 서버:

- GPU: `A10 24GB`
- CPU: `12~16 vCPU`
- RAM: `32~64GB`

추천 상황:

- 이미 A10 장비 접근성이 있는 경우
- 온프렘 GPU 서버

## 15.3 예산 절약형

### `NVIDIA T4` 1장

권장 서버:

- GPU: `T4 16GB`
- CPU: `8~12 vCPU`
- RAM: `24~32GB`

주의:

- 지금은 돌아갈 수 있어도, 이후 mask/segmentation/자연화까지 넣으면 금방 답답해질 수 있다.
- 데모/개발/초기 검증용에 더 가깝다.

## 15.4 권장하지 않는 시작점

### CPU only 서버

가능한 경우:

- 개발 환경
- benchmark
- 로컬 디버깅

권장하지 않는 이유:

- 앞으로 하고 싶은 작업이 대부분 CPU에 불리하다.
- 자연화와 비디오 파이프라인이 붙으면 금방 한계가 온다.

### A100/H100 급

권장하지 않는 이유:

- 현재 서비스 단계에서 비용 대비 과하다.
- 지금 필요한 것은 대규모 모델 학습보다 "실시간 영상 파이프라인 최적화"다.

---

## 16. GPU 서버를 사도 바로 빨라지지 않는 이유

이건 매우 중요하다.

현재 코드의 핵심 렌더 경로는 아직 GPU를 직접 활용하지 않는다.

현재 서버 렌더는 대략 아래 코드 경로다.

- `Inference/app/rtc.py`
- `Inference/app/server_render.py`
- `Pillow`
- `PyAV`

즉, 지금 GPU 서버를 붙이면 아래 이점은 있다.

- 앞으로 GPU 기반 추론/합성으로 옮기기 쉬움
- 미디어 서버를 별도 역할로 분리 가능
- 운영 구조가 정리됨

하지만 아래는 자동으로 얻어지지 않는다.

- GPU 가속 warp
- GPU 세그멘테이션
- GPU 기반 mask/post-process
- 하드웨어 인코딩 최적화

따라서 GPU 서버 도입은 "인프라 방향"으로는 맞지만, 코드도 같이 옮겨야 진짜 효과가 난다.

---

## 17. 별도 GPU 서버로 분리할 때 유지할 것

가급적 아래 계약은 유지하는 것이 좋다.

### 유지 권장

- BE의 `hairapplybootstrap` / `hairapplyresume` 흐름
- `apply_session_id`
- connect ticket 기반 인증
- static bootstrap 응답 형식
- feature schema version / transform version 계약

### 바뀌어도 되는 것

- `APP_INFERENCE_WS_BASE_URL`
- `APP_INFERENCE_RTC_OFFER_URL`
- ICE 서버 정보
- nginx 프록시 위치
- compose 배치

즉, "사용자 세션을 여는 방식"은 유지하고, "실제 media/inference 서버의 물리적 위치"만 분리하는 것이 가장 안전하다.

---

## 18. 분리 후 권장 배포 토폴로지

권장 구조는 아래와 같다.

### API 서버

- Spring Boot
- Postgres
- Redis
- nginx

역할:

- 인증
- bootstrap API
- 일반 서비스 API

### Inference GPU 서버

- Python Inference
- RTC offer/answer
- media/render
- 필요 시 coturn 근접 배치 또는 별도 공용 TURN 사용

역할:

- 실시간 track 수신/렌더/송신
- feature 처리
- GPU 추론

### static 서버

선택지:

- 현재처럼 nginx에서 `/static`
- object storage + CDN

데이터셋이 커지면 CDN/object storage 분리도 고려할 수 있다.

---

## 19. 새 담당자가 첫날 해야 할 확인 순서

### 19.1 구조 이해

아래 파일부터 읽는다.

1. `Inference/GPU_SERVER_AGENT_GUIDE.md`
2. `HANDOFF_2026-03-17.md`
3. `Inference/README.md`
4. `Inference/ARCHITECTURE.md`
5. `BE/src/main/java/com/example/beapp/service/HomeService.java`
6. `Inference/app/main.py`
7. `Inference/app/rtc.py`
8. `Inference/app/server_render.py`

### 19.2 로컬 기동

기준 compose:

- 로컬: `BE/docker-compose.local.yml`
- 운영 유사: `BE/docker-compose.yml`

주요 명령:

```bash
docker compose -f BE/docker-compose.local.yml up -d --build
docker compose -f BE/docker-compose.local.yml ps
docker compose -f BE/docker-compose.local.yml logs -f inference
```

### 19.3 FE 최신화

```bash
corepack pnpm --dir FE build
rsync -a --delete FE/dist/ BE/nginx/html/
```

### 19.4 확인 포인트

- `https://localhost/` 접속 여부
- `https://localhost/camera` 접속 여부
- 헤어 선택 시 bootstrap 성공 여부
- `POST /rtc/inference/offer` 성공 여부
- inference 로그에서
  - `rtc offer accepted`
  - `rtc video track received`
  - `rtc data channel opened`
  - `rtc feature processed`
  가 찍히는지

---

## 20. 지금 당장 조심해야 하는 계약

아래를 함부로 바꾸면 FE/BE/Inference가 조용히 어긋날 수 있다.

### 절대 무심코 바꾸지 말 것

- `feature_schema_version`
- `transform_version`
- `coordinate_space`
- `anchor_set`
- JWT secret / issuer
- `hair_rgba`가 이미 crop된 이미지라는 가정
- asset metadata key 이름

### 바꿀 때 반드시 같이 봐야 하는 파일

- `FE/src/lib/Camera/inference.ts`
- `Inference/app/models.py`
- `Inference/app/render.py`
- `Inference/app/catalog.py`
- `BE/src/main/java/com/example/beapp/service/HomeService.java`

---

## 21. 현재 기준 추천 작업 우선순위

지금 기준으로 인프런스 담당자가 우선순위를 잡는다면 아래 순서가 맞다.

### 1순위

- RTC 경로의 초기 안정화
- remote video 전환 timing 개선
- frame-feature 동기화 개선
- in-flight feature 정책 개선

### 2순위

- 서버 렌더 품질 개선
- 기존 머리 제거
- face/protect mask 처리
- 복수 레이어 합성

### 3순위

- GPU 경로 도입
- segmentation/matting을 GPU로 이동
- OpenCV CUDA / Torch / TensorRT / NVENC 검토

### 4순위

- 별도 GPU 서버 운영 자동화
- 모니터링
- 동시 세션 부하 테스트

---

## 22. 운영자가 마지막으로 기억해야 하는 핵심 요약

이 저장소의 핵심은 아래 한 줄로 정리된다.

`BE가 세션과 티켓을 만들고, FE가 얼굴 feature를 만들고, Inference가 가장 맞는 헤어를 골라 실시간 렌더를 담당한다.`

그리고 앞으로의 방향은 아래 한 줄이다.

`초기에는 same-server로 빠르게 검증하고, 최종적으로는 Inference를 별도 GPU 미디어 서버로 분리한다.`

현재 기준 판단은 명확하다.

- 아키텍처 방향: `GPU 서버 분리`가 맞다.
- 현재 코드 상태: 아직 완전한 GPU 파이프라인은 아니다.
- 당장 중요한 일: `RTC 안정화 + 동기화 개선 + 서버 렌더 품질 개선`
- 그 다음: `GPU 경로 최적화`

이 문서만 읽고도 새 담당자는 아래를 바로 이해할 수 있어야 한다.

- 어디서 세션이 시작되는지
- 어디서 feature가 만들어지는지
- 어디서 asset이 골라지는지
- 왜 지금 느리고 왜 튀는지
- GPU 서버를 왜 붙여야 하는지
- 어느 파일부터 수정해야 하는지

이 기준이 맞다.
