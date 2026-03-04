# Local / Remote Handoff Guide

목적: 다른 PC에서 이 프로젝트를 이어서 개발·운영할 때 필요한 최소 설정과 명령 모음.

## 필수 도구
1. JDK 21 (Temurin/Corretto 아무거나).
2. Docker + Docker Compose 플러그인.
3. VS Code(추천) + 다음 익스텐션: Remote SSH, Java Extension Pack, Spring Boot Extension Pack, Lombok.

## 코드 준비
```bash
git clone <repo-url>
cd S14P21M101/BE
./gradlew test --no-daemon
```

## 로컬 개발 실행
```bash
# 개발용 HTTPS 스택(앱+Postgres+RabbitMQ+Nginx)
docker compose up --build
```
접속 포트: 앱 8081, Nginx HTTP 8082(→HTTPS 리다이렉트), Nginx HTTPS 8443, Postgres 5432, RabbitMQ 5672/15672.  
헬스체크: `curl -k https://localhost:8443/api/health` → `test: 성공!!`

## 서버(EC2) 운영 메모
- Nginx/CORS/HTTPS 설정: `/etc/nginx/sites-available/sslip.conf` (링크는 `/etc/nginx/sites-enabled/sslip.conf`).  
- 도메인: `43.200.171.60.sslip.io` (Let’s Encrypt 실서명). 인증서 경로: `/etc/letsencrypt/live/43.200.171.60.sslip.io/`.
- 갱신 테스트: `sudo certbot renew --dry-run --no-random-sleep-on-renew`. 갱신 훅: `/etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh` (nginx reload).
- 헬스체크: `curl -i https://43.200.171.60.sslip.io/api/health` (CORS 허용, UTF-8).
- Jenkins: 패키지 설치, 서비스 실행 중 (`systemctl status jenkins`). 초기 비밀번호는 `/var/lib/jenkins/secrets/initialAdminPassword`.

## 백엔드 연동 시
- `/etc/nginx/sites-available/sslip.conf`의 `/api/` 프록시 블록 주석 해제 후 reload:
  - `sudo systemctl reload nginx`
- 프록시 CORS/OPTIONS 헤더는 이미 포함되어 있음.

## 흔한 문제
- CORS 오류: Nginx 설정이 최신인지 확인 후 reload.
- 인증서 만료: certbot 타이머 기본 활성화. 수동 갱신 시 위 dry-run 명령으로 점검.
- 포트 충돌: 로컬 8080이 다른 서비스와 겹치면 `docker-compose.yml` 포트를 조정.
