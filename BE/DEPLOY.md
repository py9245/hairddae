# Backend Docker Compose Stack

구성: Spring Boot(app), PostgreSQL, RabbitMQ, Nginx(SSL 리버스 프록시).

## 빌드 & 실행
```bash
cd /home/ubuntu/S14P21M101/BE
# (최초 1회) self-signed 인증서 생성
./scripts/generate-selfsigned.sh

# 도커 빌드 및 기동
docker compose up --build
```

포트 매핑
- 앱 직접 접근: http://localhost:8081 (컨테이너 8080)
- Nginx HTTP: http://localhost:8082 (자동 301 → HTTPS)
- Nginx HTTPS: https://localhost:8443
- Postgres: localhost:5432 (user: appuser / pass: apppass / db: appdb)
- RabbitMQ: amqp://localhost:5672, 콘솔 http://localhost:15672 (guest/guest)

## Spring 프로파일
- 기본: 외부 DB 없이도 실행 가능.
- `docker` 프로파일: Postgres/RabbitMQ 컨테이너 연결 설정 사용.
  - 도커 컴포즈에서 `SPRING_PROFILES_ACTIVE=docker` 설정됨.

## API 확인
```bash
curl -k https://localhost:8443/test
# 응답 예: {"status":"success","message":"ok"}
```

## 주요 파일
- [docker-compose.yml](/home/ubuntu/S14P21M101/BE/docker-compose.yml)
- [Dockerfile](/home/ubuntu/S14P21M101/BE/Dockerfile)
- Nginx 설정: [nginx/conf.d/app.conf](/home/ubuntu/S14P21M101/BE/nginx/conf.d/app.conf)
- 인증서: [nginx/certs/selfsigned.crt](/home/ubuntu/S14P21M101/BE/nginx/certs/selfsigned.crt), [.key](/home/ubuntu/S14P21M101/BE/nginx/certs/selfsigned.key)
- Self-signed 생성 스크립트: [scripts/generate-selfsigned.sh](/home/ubuntu/S14P21M101/BE/scripts/generate-selfsigned.sh)
- 테스트 엔드포인트: [TestController.java](/home/ubuntu/S14P21M101/BE/src/main/java/com/example/backend/api/TestController.java)

## 운영/보안 참고
- self-signed는 개발용만 사용. 운영 시 정식 인증서로 교체하고 `nginx/certs`에 배치.
- DB/Rabbit 자격증명을 환경변수나 비밀관리로 교체 권장.
- 필요 시 Nginx 포트 매핑(8082/8443)을 환경에 맞게 조정.
