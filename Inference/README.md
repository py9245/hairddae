# Inference Service

`Inference/`는 헤어 apply의 WebRTC 중심 inference 서비스를 담는다.
  
새로 합류한 인프런스 서버 담당자나 GPU 서버 분리 작업자는 먼저 [`GPU_SERVER_AGENT_GUIDE.md`](/home/ubuntu/S14P21M101/Inference/GPU_SERVER_AGENT_GUIDE.md) 를 읽는 것을 권장한다.

## 현재 배포 방식

현재 same-server 배포에서는 `Inference` 전용 `docker-compose.yml`을 두지 않는다.

이유:

- 실제 배포 단위가 `nginx + app + inference + redis + postgres` 하나의 네트워크여야 한다.
- Jenkins도 `BE/docker-compose.yml` 하나로 same-server 스택을 올리는 방식이다.
- 따라서 현재 기준의 운영 compose 엔트리포인트는 [`BE/docker-compose.yml`](/home/ubuntu/S14P21M101/BE/docker-compose.yml) 과 [`BE/docker-compose.local.yml`](/home/ubuntu/S14P21M101/BE/docker-compose.local.yml) 이다.

즉, `Inference`는 compose를 "안 쓰는" 것이 아니라, `BE` 쪽 상위 compose에 서비스로 포함되어 있다.

## 언제 별도 compose를 두는가

별도 `Inference/docker-compose.yml`은 다음 상황에서만 고려한다.

- GPU 서버에 inference만 따로 배포할 때
- 로컬에서 `BE/nginx/postgres/redis` 없이 inference만 독립 실행하고 싶을 때

현재 브랜치 목표인 same-server MVP에서는 별도 compose보다 상위 compose 일원화가 낫다.

GPU 서버에서 inference 단독 배포가 필요하면 [`docker-compose.gpu.yml`](/home/ubuntu/S14P21M101/Inference/docker-compose.gpu.yml) 과 [`Dockerfile.gpu`](/home/ubuntu/S14P21M101/Inference/Dockerfile.gpu) 를 사용한다.

## 로컬 실행

직접 실행:

```bash
cd Inference
uv sync --dev --frozen
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8090
```

HTTP 프레임 테스트까지 켜서 실행:

```bash
cd Inference
INFERENCE_STATIC_ROOT=/home/ubuntu/S14P21M101/static \
INFERENCE_FACE_LANDMARKER_MODEL_PATH=/home/ubuntu/S14P21M101/Inference/models/face_landmarker.task \
INFERENCE_HAIR_SEGMENTER_MODEL_PATH=/home/ubuntu/S14P21M101/Inference/models/hair_segmenter.tflite \
INFERENCE_HTTP_TEST_ENABLED=true \
uv run uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8090
```

HTTP health 확인:

```bash
curl "http://127.0.0.1:8090/api/runtime/health?dataset_code=0001"
```

가속 상태 확인:

```bash
curl "http://127.0.0.1:8090/healthz"
curl "http://127.0.0.1:8090/api/runtime/health?dataset_code=0001"
```

응답의 `acceleration` 필드에서 현재 런타임이 GPU를 실제로 보고 있는지, OpenCV CUDA `warpAffine/alphaComp` 까지 사용 가능한지 확인할 수 있다.

## GPU 서버 실행

```bash
cd Inference
docker compose -f docker-compose.gpu.yml up -d --build
```

권장 환경 변수:

- `INFERENCE_MEDIAPIPE_DELEGATE=gpu`
- `INFERENCE_RENDER_ACCELERATION=opencv_cuda`
- `INFERENCE_RTC_FACE_LANDMARKER_RUNNING_MODE=video`
- `INFERENCE_RTC_HAIR_SEGMENTER_RUNNING_MODE=video`
- `INFERENCE_RTC_SESSION_LOCAL_PROCESSORS=true`

주의:

- 기본 [`Dockerfile`](/home/ubuntu/S14P21M101/Inference/Dockerfile) 은 `opencv-python-headless` CPU 휠을 설치한다.
- [`Dockerfile.gpu`](/home/ubuntu/S14P21M101/Inference/Dockerfile.gpu) 은 `opencv-python` 공식 저장소를 빌드해 CUDA OpenCV 휠을 만든 뒤 런타임에 주입한다.
- MediaPipe GPU delegate는 런타임이 GPU 디바이스를 노출할 때만 활성화된다.

HTTP 프레임 테스트:

```bash
curl -X POST \
  "http://127.0.0.1:8090/api/runtime/frame?dataset_code=0001&hair_id=1&apply_session_id=local-http-test&response_format=jpeg" \
  -H "content-type: image/jpeg" \
  --data-binary @/path/to/frame.jpg \
  -o rendered.jpg -D runtime_headers.txt
```

이 경로는 내부/local 검증용이다. 운영 프록시에는 그대로 외부 공개하지 않는 편이 맞다.

테스트:

```bash
cd Inference
uv sync --dev --frozen
uv run pytest
```

## 환경 변수

추적 가능한 예시는 [`Inference/.env.example`](/home/ubuntu/S14P21M101/Inference/.env.example) 에 둔다.

중요:

- same-server deploy에서는 `APP_SECURITY_JWT_SECRET`, `APP_SECURITY_JWT_ISSUER`가 `BE`와 반드시 같아야 한다.
- 실제 운영에서는 `.env.example`를 복사해 별도 `.env`를 만들거나, Jenkins/compose env로 주입한다.
