# hairddae.store 배포 가이드 (FE 전용)

## 개요
- 정적 FE(Vite) 빌드 산출물(`dist`)을 Nginx로 서비스.
- CI/CD는 FE 디렉터리 안의 Jenkins 파이프라인(`FE/Jenkinsfile`) 사용.
- 도메인: `hairddae.store` (추가로 `www` 서브도메인 리다이렉트 포함).
- 배포는 `releases/<타임스탬프>` 디렉터리로 업로드 후 `current` 심볼릭 링크를 전환하는 방식(사실상 무중단).

## 선행 준비
1) DNS
- `hairddae.store`, `www.hairddae.store`를 서비스 서버의 공인 IP로 A 레코드 설정.

2) 서버 패키지
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx rsync
sudo mkdir -p /var/www/hairddae
sudo chown -R $USER:$USER /var/www/hairddae
```

3) Nginx 사이트 설정
- 파일: `FE/deploy/nginx/hairddae.store.conf`를 서버의 `/etc/nginx/sites-available/`에 배치.
```bash
sudo cp hairddae.store.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/hairddae.store.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
- HTTPS 발급 (Let's Encrypt, nginx 설정이 80포트만 열려 있어야 함):
```bash
sudo certbot --nginx -d hairddae.store -d www.hairddae.store
sudo systemctl reload nginx
```

## Jenkins 설정
1) Node.js 설치
- Jenkins 에이전트에 Node 20.x 설치 후 **Global Tool Configuration**에서 이름 `node20`으로 등록.

2) SSH 크리덴셜
- 대상 서버에 배포용 SSH 키를 등록(비번 없이 접속 가능하게 `~/.ssh/authorized_keys`).
- Jenkins에 **Credentials** 추가: 유형 `SSH Username with private key`, ID `hairddae-ssh`, 사용자 예: `ubuntu`.

3) 잡(멀티브랜치 권장)
- 리포지토리 브랜치: `FE` 기준 배포.
- 환경 변수(필요시 파이프라인 파라미터로 정의):
  - `DEPLOY_HOST`: 배포 대상 서버 IP 또는 호스트명
  - `DEPLOY_USER`: SSH 사용자 (기본 `ubuntu`)
  - `DEPLOY_PATH`: 기본 `/var/www/hairddae`
  - `RELEASE_KEEP`: 보존할 릴리즈 개수(기본 3)
  - 현재 기본값: `DEPLOY_HOST=13.125.75.148`, `DEPLOY_USER=ubuntu`, `DEPLOY_PATH=/var/www/hairddae`
  - 멀티브랜치/파이프라인 설정 시 Script Path: `FE/Jenkinsfile`

## 배포 흐름(Jenkinsfile 요약)
1) Install: `FE` 디렉터리에서 `npm ci --prefer-offline` (캐시 `${WORKSPACE}/.npm`).
2) Build: `npm run build` -> `dist` 생성.
3) Deploy (`FE` 브랜치만):
   - `releases/<타임스탬프>` 경로 생성 후 `dist/` 내용을 해당 디렉터리로 rsync
   - `current` 심볼릭 링크를 새 릴리즈로 원자적 전환(브라우저는 새/구 버전 간섭 없이 서비스)
   - 오래된 릴리즈는 `RELEASE_KEEP` 값만큼 남기고 정리
   - `sudo systemctl reload nginx` (필요 시)
4) 빌드 산출물 아카이브: `dist/**`를 Jenkins에 보관.

## 수동 롤백(간단)
- 서버에서 이전 릴리즈로 심볼릭 링크만 돌리면 됨:
```bash
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "cd /var/www/hairddae/releases && ls -1tr"
# 목록에서 이전 릴리즈 이름을 확인한 뒤:
ssh ${DEPLOY_USER}@${DEPLOY_HOST} "ln -sfn /var/www/hairddae/releases/<이전릴리즈> /var/www/hairddae/current && sudo systemctl reload nginx"
```

## GitLab Pages 파이프라인 중단
- `.gitlab-ci.yml`은 더 이상 사용하지 않음. GitLab CI가 실행된다면 프로젝트 Settings → CI/CD → General pipelines에서 비활성화하거나 파일을 제거하세요.
