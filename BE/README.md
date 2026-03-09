# BE 서비스 개요

- Spring Boot 3.3 + Java 21
- Gradle 기반
- Postgres, Redis, Nginx 리버스 프록시를 포함한 `docker-compose` 템플릿 제공

## 로컬 실행
```
./gradlew bootRun
```
필요 환경변수는 [.env.example](/home/ubuntu/S14P21M101/BE/.env.example)를 참고해 `.env`로 복사해 사용하세요.

## Docker 실행
```
docker compose up --build
```
- 외부 노출 포트: 80 (Nginx). 애플리케이션 8080 포트는 컴포즈 네트워크 내부에서만 접근.
- 정적 파일은 `nginx/html`에 배포하면 `/` 경로로 서빙됩니다.

## 기본 엔드포인트
- `GET /api/health` : 헬스 체크 JSON
- `GET /actuator/health` : Spring Actuator 헬스

## 인증
기본 Basic Auth 계정은 `.env` 혹은 `application.yml`의 `APP_SECURITY_USER`, `APP_SECURITY_PASSWORD`로 설정됩니다. 운영에서는 필수로 변경하세요.
