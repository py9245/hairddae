# Hairddae FE (React + Vite)

프론트엔드 전용 폴더입니다. 배포는 Jenkins → Nginx(hairddae.store)로 진행합니다.

## 빠른 시작
```bash
npm ci
npm run dev   # http://localhost:5173
npm run build # dist 생성
```

## 로컬 개발자가 해야 할 것 (FE 브랜치 기준)
1) 리포지토리 클론/업데이트
```bash
git clone <repo> S14P21M101   # 최초 1회
cd S14P21M101
git checkout FE
git pull origin FE
```

2) 환경변수 파일 준비
```bash
cp FE/.env.example FE/.env.local
# 필요 시 값 수정 (VITE_APP_NAME, 추후 VITE_API_BASE_URL 등)
```

3) 의존성 설치 & 로컬 실행
```bash
cd FE
npm ci
npm run dev   # http://localhost:5173
```

4) 빌드 테스트
```bash
npm run build  # dist 생성 확인
```

5) 변경사항 커밋/푸시 (FE 브랜치)
```bash
git status
git add <files>
git commit -m "feat: ..."
git push origin FE
```
- GitLab 웹훅 → Jenkins → Nginx 순으로 자동 배포(무중단) 진행
- 배포 후 https://hairddae.store 로 확인

6) 배포 결과 검증(옵션)
```bash
curl -I https://hairddae.store
```

## 환경변수
- 예시 파일: `.env.example`
- 로컬 개발 시 `.env.local` 등에 설정 후 사용 (gitignore 적용됨).
```
VITE_APP_NAME=Hairddae FE
# VITE_API_BASE_URL=https://api.hairddae.store
```

## 배포 (FE 브랜치)
- Jenkins Script Path: `FE/Jenkinsfile`
- Branch: `FE`
- 배포 대상: `/var/www/hairddae` (releases/<timestamp> → current 심볼릭 링크 전환)
- Nginx 설정: `deploy/nginx/hairddae.store.conf`
- 도메인: `hairddae.store` (`www` 포함), SSL은 certbot --nginx 사용

## 주요 파일
- `src/config/env.js` : 환경변수 모음 (기본값 포함)
- `src/App.jsx`       : 시작 화면, `VITE_APP_NAME` 표시
- `deploy/README.md`  : 서버 설정/배포 가이드
