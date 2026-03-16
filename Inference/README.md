# Inference Service

`Inference/`는 헤어 apply의 feature-only WebSocket inference 서비스를 담는다.

## 현재 배포 방식

현재 same-server 배포에서는 `Inference` 전용 `docker-compose.yml`을 두지 않는다.

이유:

- 실제 배포 단위가 `nginx + app + inference + redis + postgres` 하나의 네트워크여야 한다.
- Jenkins도 `BE/docker-compose.yml` 하나로 same-server 스택을 올리는 방식이다.
- 따라서 현재 기준의 운영 compose 엔트리포인트는 [`BE/docker-compose.yml`](/home/yusin/S14P21M101/BE/docker-compose.yml) 과 [`BE/docker-compose.local.yml`](/home/yusin/S14P21M101/BE/docker-compose.local.yml) 이다.

즉, `Inference`는 compose를 "안 쓰는" 것이 아니라, `BE` 쪽 상위 compose에 서비스로 포함되어 있다.

## 언제 별도 compose를 두는가

별도 `Inference/docker-compose.yml`은 다음 상황에서만 고려한다.

- GPU 서버에 inference만 따로 배포할 때
- 로컬에서 `BE/nginx/postgres/redis` 없이 inference만 독립 실행하고 싶을 때

현재 브랜치 목표인 same-server MVP에서는 별도 compose보다 상위 compose 일원화가 낫다.

## 로컬 실행

직접 실행:

```bash
cd Inference
uv sync --dev --frozen
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8090 --ws-ping-interval 15 --ws-ping-timeout 10
```

테스트:

```bash
cd Inference
uv sync --dev --frozen
uv run pytest
```

## 환경 변수

추적 가능한 예시는 [`Inference/.env.example`](/home/yusin/S14P21M101/Inference/.env.example) 에 둔다.

중요:

- same-server deploy에서는 `APP_SECURITY_JWT_SECRET`, `APP_SECURITY_JWT_ISSUER`가 `BE`와 반드시 같아야 한다.
- 실제 운영에서는 `.env.example`를 복사해 별도 `.env`를 만들거나, Jenkins/compose env로 주입한다.
