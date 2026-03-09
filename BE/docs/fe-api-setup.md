# FE → BE 통신 가이드 (j14m101.p.ssafy.io 단일 도메인)

## 베이스 URL
- 프로덕션: `https://j14m101.p.ssafy.io`
- API는 상대경로로 호출: `fetch('/api/…')`
- 헬스체크: `/api/health`, `/api/accounts/health`, `/api/mypage/health`, `/api/home/health`

## 개발 환경 (Vite 예시)
`vite.config.ts`에 프록시 한 줄만 추가하면 코드 변경 없이 `/api`를 그대로 쓸 수 있습니다.
```ts
export default defineConfig({
  server: {
    proxy: { '/api': 'http://localhost:8080' }
  }
});
```

## 인증/헤더
- 현재 기본 Basic Auth가 켜져 있음. `Authorization: Basic base64(user:pass)` 헤더 필요. 실제 운용 전 비밀번호 교체 및 토큰/세션 방식으로 대체 권장.
- 쿠키 인증을 쓴다면 `Secure`, `HttpOnly`, `SameSite=Lax` 이상 적용.

## 오류/타임아웃 권장값
- 요청 타임아웃: 10~15초 권장.
- 업로드 한도: Nginx `client_max_body_size 10m` 기준으로 맞춰서 FE 측도 10MB 이하로 제한.

## 배포 시 유의사항
- FE 빌드 산출물은 `/home/ubuntu/S14P21M101/BE/nginx/html/`에 배포됩니다.
- TLS 인증서는 `/home/ubuntu/S14P21M101/BE/nginx/certs/` 아래 `live/j14m101.p.ssafy.io/*` 구조로 배치하고 `docker compose up --build` 후 적용됩니다.
- 도메인은 `j14m101.p.ssafy.io` 한 개만 사용하고, `/api` 경로로 백엔드와 통신합니다. 추가 하위 도메인이 필요하면 Nginx에 서버블록만 추가하면 됩니다.
