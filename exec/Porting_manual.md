# hairddae 프로젝트 포팅 매뉴얼(Porting Manual)

## 1. 개발 환경 정보

* **Front-end:** React 19.2.0, TypeScript 5.9.3, Vite 7.3.1, pnpm  
* **Back-end:** Java 21, Spring Boot, Gradle  
* **AI:** Python, MediaPipe, OpenCV, Bisnet  
* **Database:** PostgreSQL(RDBMS), Redis(Cache)   
* **Infra:** Docker & Docker Compose, Nginx  
* **CI/CD & IDE:** GitLab, Jenkins, Swagger, VS Code 

## 2. 빌드 및 배포 방법

### Front-end

소스코드 클론 진행
```
git clone https://lab.ssafy.com/s14-ai-image-sub1/S14P21M101.git 
```
소스코드 클론 완료 후 프로젝트 루트 디렉토리 이동
```
cd S14P2M101
```

FE 폴더로 이동
```
cd FE
```

아래 명령어로 의존성 패키지 설치
```
pnpm install
```

아래 명령어 실행
```
pnpm run dev
```

### Back-end

**사전 요구사항:** Docker 및 Docker Compose 설치 및 실행  
소스코드 클론 진행
```
git clone https://lab.ssafy.com/s14-ai-image-sub1/S14P21M101.git 
```
소스코드 클론 후 프로젝트 루트 디렉토리 이동
```
cd S14P2M101
```

BE 폴더로 이동
```
cd BE
```

아래 명령어로 환경변수 파일 생성 후  환경 변수 추가(동일 위치에 env_example.txt 참조)
```
touch .env
```

도커 컨테이너 빌드 및 실행
```
docker compose up -d -build
```

## 3. 환경 변수 설정(.env)

빌드 시 필요한 주요 환경 변수 목록이 적혀있는 파일 확인
* Backend 환경 변수 -> exec/env_back.md 참조
* Frontend 환경 변수 -> exec/env_front.md 참조

### DB 접속 및 프로퍼티

* **사용자:** beapp  
* **데이터베이스명:** beapp  
* **포트:** 5432  
* **주요 테이블:**   
  * `users`, `jobs`, `histories`, `hairs`, `hair_likes`, `flyway_schema_history`