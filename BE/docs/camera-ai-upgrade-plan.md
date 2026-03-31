# Camera AI Upgrade API 계획

작성일: 2026-03-31

## 목적

사용자가 헤어 적용 화면에서 캡처한 이미지를 기준으로 `AI 보정`을 요청하면,
`BE`가 해당 이미지를 받아 `GMS` 모델에 프롬프트와 함께 전달하고,
생성된 결과 이미지를 다시 클라이언트에 반환하는 흐름을 설계한다.

기본 전제는 아래와 같다.

- 사용자는 로그인된 상태다.
- 인증은 쿠키 기반으로 이미 완료되어 있다.
- `userId` 는 프론트가 보내지 않는다.
- 현재 사용자는 `BE`가 인증 컨텍스트에서 직접 식별한다.

1차 대상 API 는 아래 경로로 고정한다.

- `POST /api/camera/ai-upgrade/`

## 1차 권장 방향

1차 구현은 `동기 POST 1회`로 가는 것을 권장한다.

이유는 아래와 같다.

- 사용자 경험이 단순하다.
- `FE`가 별도 polling 타이밍을 관리할 필요가 없다.
- 구현 복잡도가 낮다.
- 현재 기능은 `캡처 이미지 1장 -> AI 보정 결과 1장` 흐름으로 단순하다.

즉 1차에서는 `jobs` 기반 비동기 처리보다 아래 흐름을 우선한다.

1. 클라이언트가 캡처 이미지를 업로드한다.
2. `BE`가 현재 로그인 사용자를 인증 컨텍스트에서 확인한다.
3. `BE`가 고정 프롬프트를 조합해 `GMS`에 이미지와 함께 요청한다.
4. `BE`가 결과 이미지를 저장하거나 즉시 반환한다.
5. `FE`는 단일 응답으로 결과를 받는다.

## API 계약 초안

### 엔드포인트

- `POST /api/camera/ai-upgrade/`
- `Content-Type: multipart/form-data`
- 인증 필요: `authenticated()`

### 요청 필드

- `image`: 필수, 캡처 원본 이미지 파일
- `device_id`: 선택, 클라이언트 추적 또는 로그 분석용

중요:

- `userId` 는 받지 않는다.
- `hair_id` 는 1차에서 받지 않는다.
- 프롬프트는 전부 `BE`가 조합한다.

### 요청 예시

브라우저는 파일 선택 업로드가 아니라, 캡처한 `Blob` 또는 `File` 을 그대로 전송하면 된다.

```ts
const formData = new FormData();
formData.append('image', captureBlob, 'capture.png');
formData.append('device_id', deviceId);

await fetch('/api/camera/ai-upgrade/', {
  method: 'POST',
  body: formData,
  credentials: 'include',
});
```

### 응답 예시

```json
{
  "code": 200,
  "message": "AI 보정 완료",
  "success": true,
  "request_id": "9d3d68d0-2dc4-4f54-bfcb-e6d18a6ca248",
  "result_image_url": "/static/camera-ai/9d3d68d0-2dc4-4f54-bfcb-e6d18a6ca248/result.png"
}
```

필요하면 아래 정보를 추가로 내려줄 수 있다.

- `provider`: `gms`
- `model`: 사용한 모델명
- `processing_ms`: 처리 시간

## 인증 정책

기본 정책은 `로그인 + 쿠키 인증 완료 사용자만 허용`이다.

원칙은 아래와 같다.

- 요청 본문에 `userId` 를 받지 않는다.
- 현재 로그인 사용자는 `Authentication` 에서 확인한다.
- 인증 실패 시 즉시 `401` 로 종료한다.

즉 이 API 는 아래 성격이다.

- `POST /api/camera/ai-upgrade/` 는 인증 사용자 전용
- `credentials: 'include'` 기반 호출 전제

## 프롬프트 구성 원칙

프롬프트는 `FE`가 만들지 않고 `BE`가 고정 규칙으로 만든다.

이유는 아래와 같다.

- 결과 품질을 일정하게 유지하기 쉽다.
- 프롬프트 유출과 임의 변경을 줄일 수 있다.
- 운영 중 프롬프트를 서버에서 일괄 조정할 수 있다.

## 프롬프트 방향

현재 목적은 `사용자가 이미 적용한 헤어스타일이 보이는 캡처 이미지`를 더 자연스럽게 보정하는 것이다.

즉 `GMS`는 아래를 입력으로 받는다.

- 캡처 이미지 1장
- `BE`가 만든 고정 프롬프트

1차 프롬프트 핵심 방향은 아래와 같다.

- 헤어 영역은 자연스럽게 보정할 것
- 현재 이미지에 보이는 헤어스타일은 유지할 것
- 눈썹 아래 영역은 수정하지 말 것
- 눈, 코, 입, 피부, 얼굴형은 변경하지 말 것
- 원본 인물 동일성을 유지할 것
- 배경과 의상은 변경하지 말 것
- 전체 이미지를 자연스럽고 선명하게 정리할 것

중요:

- 1차에서는 `hair_id` 나 헤어 메타데이터 없이 진행한다.
- 현재 캡처 이미지 자체가 이미 원하는 헤어 상태를 담고 있다고 본다.

## 백엔드 구성 제안

### Controller

- `api/CameraController`

역할:

- `POST /api/camera/ai-upgrade/`

### DTO

- `api/dto/camera/CameraAiUpgradeResponse`

주의:

- 요청은 `multipart/form-data` 이므로
- `@RequestPart("image") MultipartFile image`
- `@RequestParam(value = "device_id", required = false) String deviceId`
- 형태가 가장 단순하다.

### Service

- `service/CameraAiUpgradeService`
- `service/GmsImageGenerationClient`

역할 분리:

- `CameraAiUpgradeService`
  - 인증 사용자 식별
  - 이미지 검증
  - 프롬프트 조합
  - `GMS` 호출 위임
  - 결과 이미지 저장
  - 응답 생성
- `GmsImageGenerationClient`
  - 외부 `GMS` HTTP 호출
  - 인증 헤더 추가
  - 요청/응답 변환
  - 타임아웃 및 오류 처리

## 설정값 제안

`application.yml` 에 아래 영역을 추가하는 방안을 권장한다.

```yml
app:
  camera-ai:
    enabled: ${APP_CAMERA_AI_ENABLED:true}
    provider-base-url: ${GMS_BASE_URL}
    provider-auth-token: ${GMS_KEY}
    model-name: ${GMS_IMAGE_MODEL:gpt-image-1-mini}
    request-timeout-ms: ${APP_CAMERA_AI_REQUEST_TIMEOUT_MS:30000}
    max-upload-size-bytes: ${APP_CAMERA_AI_MAX_UPLOAD_SIZE_BYTES:5242880}
    result-dir: ${APP_CAMERA_AI_RESULT_DIR:camera-ai}
    size: ${APP_CAMERA_AI_SIZE:1024x1024}
    quality: ${APP_CAMERA_AI_QUALITY:low}
    output-format: ${APP_CAMERA_AI_OUTPUT_FORMAT:png}
    input-fidelity: ${APP_CAMERA_AI_INPUT_FIDELITY:}
```

대응 프로퍼티 클래스:

- `config/AppCameraAiProperties`

## GMS 호출 계약

현재 사용할 대상 모델과 게이트웨이는 아래와 같다.

- 모델: `gpt-image-1-mini`
- GMS 게이트웨이 base URL: `${GMS_BASE_URL}`
- 인증: `Authorization: Bearer ${GMS_KEY}`

즉 실제 운영값은 `.env` 또는 서버 환경변수에서 아래 이름으로 주입한다.

- `GMS_BASE_URL`
- `GMS_KEY`
- `GMS_IMAGE_MODEL`

중요:

- 주신 예시는 `POST /images/generations` 이다.
- 하지만 현재 요구사항은 `텍스트만으로 새 이미지를 생성`하는 것이 아니라
- `캡처 이미지 1장을 입력으로 보내고, 그 이미지를 보정/편집`하는 흐름이다.

OpenAI 호환 공식 문서 기준으로는 아래처럼 구분된다.

- `POST /v1/images/generations`
  - 프롬프트 기반 새 이미지 생성
- `POST /v1/images/edits`
  - 입력 이미지와 프롬프트를 함께 보내는 편집/보정

즉 현재 요구사항에는 `generations` 보다 `edits` 가 더 맞다.

따라서 1차 구현 권장안은 아래와 같다.

- FE -> BE: `multipart/form-data` 로 `image` 전송
- BE -> GMS: `POST https://gms.ssafy.io/gmsapi/api.openai.com/v1/images/edits`

## GMS 요청 형식 제안

구현 기준으로는 `BE -> GMS` 구간도 `multipart/form-data` 로 전달한다.

요청 필드 예시:

```text
POST ${GMS_BASE_URL}/images/edits
Authorization: Bearer ${GMS_KEY}
Content-Type: multipart/form-data

- model: gpt-image-1-mini
- prompt: <BE가 만든 고정 프롬프트>
- image: <업로드 이미지 파일>
- n: 1
- size: 1024x1024
- quality: low
- output_format: png
- user: <BE가 인증 컨텍스트에서 읽은 userId>
```

이 방식의 장점:

- `BE`가 받은 업로드 이미지를 그대로 GMS에 전달할 수 있다.
- 별도 base64 data URL 변환 로직이 필요 없다.
- OpenAI 호환 `images/edits` 파일 업로드 방식과 맞는다.

참고:

- `gpt-image-1-mini` 는 `input_fidelity=high` 조합을 거부할 수 있으므로
- 기본값은 비워 두고, 필요할 때만 명시적으로 보내는 쪽이 안전하다.

만약 SSAFY `GMS` 가 `images/generations` 에도 입력 이미지를 허용하는 커스텀 확장을 갖고 있다면,
그 스펙 문서를 별도로 확인한 뒤 그때 맞춰 바꾸면 된다.

현재 문서 기준 기본안은 `images/edits` 다.

## 이미지 저장 방식

생성 결과는 `BE`가 저장하고 URL 을 반환하는 쪽이 가장 단순하다.

권장 저장 경로 예시:

- `/opt/be-static/camera-ai/{requestId}/result.png`

권장 반환 URL 예시:

- `/static/camera-ai/{requestId}/result.png`

이 방식은 현재 정적 파일 저장 패턴과도 잘 맞는다.

## jobs 테이블에 대한 판단

1차 구현에서는 `jobs` 테이블을 쓰지 않아도 된다.

이유는 아래와 같다.

- 현재는 단일 요청-응답 흐름이면 충분하다.
- `FE`가 별도 상태 조회를 할 필요가 없다.
- `POST` 응답 한 번으로 결과를 받는 구조가 더 단순하다.

다만 아래 상황이 생기면 2차에서 `jobs` 로 확장할 수 있다.

- `GMS` 처리 시간이 길어짐
- 응답 시간이 자주 흔들림
- 재시도와 상태조회가 필요해짐
- 생성 이력 관리가 필요해짐

## 오류 처리 원칙

아래 경우를 분리해서 처리해야 한다.

- 지원하지 않는 파일 형식
- 업로드 크기 초과
- 빈 파일 업로드
- 미인증 사용자
- 외부 `GMS` 타임아웃
- 외부 `GMS` 4xx / 5xx
- 생성 결과 없음
- `GMS` 응답에 `data[0].b64_json` 없음

추가 후보 오류 코드:

- `CAMERA_AI_DISABLED`
- `CAMERA_AI_TIMEOUT`
- `CAMERA_AI_FAILED`
- `UNSUPPORTED_IMAGE_TYPE`
- `FILE_TOO_LARGE`

## 구현 순서

1. `CameraController` 추가
2. `CameraAiUpgradeResponse` 추가
3. `AppCameraAiProperties` 추가 및 `application.yml` 반영
4. `CameraAiUpgradeService` 뼈대 구현
5. `GmsImageGenerationClient` 구현
6. 결과 이미지 저장 경로 구현
7. `SecurityConfig` 에 인증 정책 반영
8. API 응답/예외 테스트 작성

## 테스트 항목

- 정상 업로드 후 결과 URL 반환
- 잘못된 MIME 타입 차단
- 빈 파일 차단
- 미로그인 접근 차단
- `GMS` 타임아웃 처리
- `GMS` 실패 응답 처리
- 성공 시 결과 이미지 저장 및 URL 반환

## 먼저 확정할 항목

구현 전에 아래를 먼저 확정해야 한다.

1. `GMS` 정확한 호출 URL
2. `GMS` 인증 방식
3. `images/generations` 가 아니라 `images/edits` 를 쓸지 최종 확정
4. `GMS` 응답에서 `data[0].b64_json` 을 받을지 확인
5. 결과 이미지를 파일로 저장할지, 바로 응답 본문으로 줄지

## 결론

1차 구현은 아래 형태를 권장한다.

- `POST /api/camera/ai-upgrade/` 단일 호출
- 요청값은 `image` 와 선택적 `device_id`
- `userId` 는 요청으로 받지 않음
- 프롬프트는 전부 `BE`에서 생성
- `BE -> GMS` 호출은 기본적으로 `gpt-image-1-mini` + `images/edits` 기준
- `GMS` 결과 이미지를 `/static/camera-ai/...` 경로로 반환

이 구조가 현재 요구사항과 가장 단순하게 맞는다.
