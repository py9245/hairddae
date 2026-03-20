# Remote Inference Deploy

기본 배포 파이프라인은 [`BE/docker-compose.yml`](/home/yusin/S14P21M101/BE/docker-compose.yml) 과 [`BE/nginx/default.conf`](/home/yusin/S14P21M101/BE/nginx/default.conf) 를 사용한다.

즉, 실제 Jenkins 배포 기준의 remote inference 전환은 "별도 compose 파일로 갈아끼우는 것"이 아니라:

- `BE/.env` 에 remote inference 관련 값을 넣고
- 같은 `BE/docker-compose.yml` 을 그대로 사용하고
- `BE/Jenkinsfile` 은 app/nginx만 배포하는 방식이다.

## 왜 이렇게 구성하는가

- FE는 `https://...` 로 서빙된다.
- 이 상태에서 브라우저가 `http://15.164.169.221/rtc/inference/offer` 로 직접 `fetch` 하면 mixed-content 로 막힌다.
- 그래서 offer/signaling 은 메인 서버 `nginx` 가 같은 origin 인 `/rtc/inference/*`, `/ws/inference/*` 로 받고, 그 뒤에서 원격 inference 서버로 HTTP 프록시한다.
- 실제 RTC 미디어는 answer/ICE candidate 교환 이후 inference 서버와 직접 연결된다.

즉, `signaling 은 same-origin HTTPS`, `미디어는 remote inference peer` 구조다.

## 메인 서버에서 필요한 값

`.env` 에 최소한 아래 값을 맞춘다.

예시는 [`BE/.env.remote-inference.example`](/home/yusin/S14P21M101/BE/.env.remote-inference.example) 를 참고하면 된다.

```env
INFERENCE_UPSTREAM_HOST=15.164.169.221
INFERENCE_UPSTREAM_PORT=8090

APP_INFERENCE_WS_BASE_URL=wss://j14m101.p.ssafy.io/ws/inference/apply
APP_INFERENCE_RTC_OFFER_URL=https://j14m101.p.ssafy.io/rtc/inference/offer
APP_INFERENCE_RTC_ICE_SERVERS_JSON=[]
```

`APP_INFERENCE_RTC_ICE_SERVERS_JSON` 은 추후 TURN 을 붙이면 메인 서버와 inference 서버에서 같은 값으로 유지해야 한다.

## 실행

```bash
cd BE
docker compose -f docker-compose.yml up -d --build postgres redis app nginx
```

## nginx 동작

- `/api/*` 와 FE 정적 파일은 기존처럼 메인 서버가 처리한다.
- `/rtc/inference/*`, `/ws/inference/*` 는 `INFERENCE_UPSTREAM_HOST:INFERENCE_UPSTREAM_PORT` 로 프록시된다.
- 원격 inference 서버는 HTTP 로만 열려 있어도 된다. TLS 종단은 메인 nginx 가 맡는다.

## 중요한 운영 주의점

- RTC 미디어는 HTTP 프록시만으로 끝나지 않는다.
- inference 서버는 외부에서 도달 가능한 ICE candidate 를 내보내야 한다.
- Docker bridge 안의 `172.x` 주소가 answer 에 실리면 브라우저가 직접 붙지 못할 수 있다.
- 그래서 분리 서버에서는 보통 아래 둘 중 하나가 필요하다.
  - inference 를 host network 로 띄우기
  - coturn 을 두고 relay candidate 를 사용하기

현재 추가한 `Inference/docker-compose.gpu.yml` 은 host network 기준으로 잡아둔 파일이다.
