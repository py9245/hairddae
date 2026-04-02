SPRING_DATASOURCE_URL=`<postgres-jdbc-url>`
> 스프링 데이터소스 주소(SPRING_DATASOURCE_URL) : PostgreSQL에 접속하는 JDBC URL 형태의 데이터입니다. ex) jdbc:postgresql://postgres:5432/beapp

SPRING_DATASOURCE_USERNAME=`<postgres-username>`
> 스프링 데이터소스 계정명(SPRING_DATASOURCE_USERNAME) : 백엔드가 DB에 접속할 때 사용하는 문자열 형태의 계정 데이터입니다. ex) beapp

SPRING_DATASOURCE_PASSWORD=`<postgres-password>`
>스프링 데이터소스 비밀번호(SPRING_DATASOURCE_PASSWORD) : 백엔드가 DB에 접속할 때 사용하는 문자열 형태의 비밀번호 데이터입니다. ex) hairddae

POSTGRES_DB=`<postgres-database-name>`
>포스트그레 데이터베이스명(POSTGRES_DB) : Postgres에 생성된 데이터베이스 이름 문자열 형태의 데이터입니다. ex) beapp

POSTGRES_USER=`<postgres-user>`
>포스트그레 사용자명(POSTGRES_USER) : Postgres 컨테이너 또는 서버에 생성할 사용자 계정 문자열 형태의 데이터입니다. ex) beapp

POSTGRES_PASSWORD=`<postgres-user-password>`
>포스트그레 사용자 비밀번호(POSTGRES_PASSWORD) : POSTGRES_USER에 연결되는 문자열 형태의 비밀번호 데이터입니다. ex) hairddae

REDIS_HOST=`<redis-host>`
>레디스 호스트(REDIS_HOST) : 백엔드 서버가 접근할 Redis 호스트명 또는 IP 문자열 형태의 데이터입니다. ex) redis

REDIS_PORT=`<redis-port>`
>레디스 포트(REDIS_PORT) : Redis가 열려 있는 숫자 형태의 포트 데이터입니다. ex) 6379

REDIS_PASSWORD=`<redis-password>`
>레디스 비밀번호(REDIS_PASSWORD) : Redis 인증에 사용하는 문자열 형태의 비밀번호 데이터입니다. ex) hairddae

REDIS_TIMEOUT=`<redis-timeout-ms>`
>레디스 타임아웃(REDIS_TIMEOUT) : Redis 요청 제한 시간을 밀리초 숫자로 적는 데이터입니다. ex) 2000

SERVER_PORT=`<backend-server-port>`
>백엔드 서버 포트(SERVER_PORT) : Spring Boot 애플리케이션이 실행될 숫자 형태의 포트 데이터입니다. ex) 8080

APP_SECURITY_USER=`<basic-auth-username>`
>기본 인증 사용자명(APP_SECURITY_USER) : 기본 인증 기능을 사용할 때 쓰는 문자열 형태의 계정 데이터입니다. ex) admin

APP_SECURITY_PASSWORD=`<basic-auth-password>`
>기본 인증 비밀번호(APP_SECURITY_PASSWORD) : 기본 인증 기능을 사용할 때 쓰는 문자열 형태의 비밀번호 데이터입니다. ex) hairddae

APP_PUBLIC_PRIMARY_HOST=`<primary-public-host>`
>대표 공개 도메인(APP_PUBLIC_PRIMARY_HOST) : 서비스의 기본 접속 도메인을 스킴 없이 적는 문자열 형태의 데이터입니다. ex) hairddae.store

APP_PUBLIC_SECONDARY_HOST=`<secondary-public-host>`
>보조 공개 도메인(APP_PUBLIC_SECONDARY_HOST) : 추가로 허용할 서비스 도메인을 스킴 없이 적는 문자열 형태의 데이터입니다. ex) j14m101.p.ssafy.io

APP_PUBLIC_CERT_NAME=`<tls-certificate-hostname>`
>인증서 호스트명(APP_PUBLIC_CERT_NAME) : TLS 인증서 Common Name 대상으로 사용할 도메인 문자열 형태의 데이터입니다. ex) j14m101.p.ssafy.io

APP_SECURITY_CORS_ALLOWED_ORIGINS=`<comma-separated-allowed-origins>`
>CORS 허용 출처(APP_SECURITY_CORS_ALLOWED_ORIGINS) : 프론트엔드 접근 주소를 쉼표로 구분해 적는 URL 문자열 목록 데이터입니다. ex) https://hairddae.store, https://j14m101.p.ssafy.io

APP_SECURITY_JWT_SECRET=`<long-random-jwt-secret>`
>JWT 시크릿(APP_SECURITY_JWT_SECRET) : JWT 서명에 사용하는 긴 랜덤 문자열 형태의 데이터입니다. ex) 231312dfevwfq2d8sdf9sd8f7sd9f87sdf

APP_SECURITY_JWT_ISSUER=`<jwt-issuer-name>`
>JWT 발급자명(APP_SECURITY_JWT_ISSUER) : 토큰 issuer 클레임에 들어가는 문자열 형태의 데이터입니다. ex) hairddae

APP_SECURITY_JWT_ACCESS_MINUTES=`<jwt-access-token-expiry-minutes>`
>액세스 토큰 만료 시간(APP_SECURITY_JWT_ACCESS_MINUTES) : 액세스 토큰 유효 시간을 분 단위 숫자로 적는 데이터입니다. ex) 60

APP_SECURITY_JWT_REFRESH_DAYS=`<jwt-refresh-token-expiry-days>`
>리프레시 토큰 만료 시간(APP_SECURITY_JWT_REFRESH_DAYS) : 리프레시 토큰 유효 시간을 일 단위 숫자로 적는 데이터입니다. ex) 1

INFERENCE_UPSTREAM_HOST=`<inference-upstream-host>`
>추론 서버 호스트(INFERENCE_UPSTREAM_HOST) : 백엔드가 프록시할 inference 서버의 호스트명 또는 IP 문자열 형태의 데이터입니다. ex) 3.35.4.105

INFERENCE_UPSTREAM_PORT=`<inference-upstream-port>`
>추론 서버 포트(INFERENCE_UPSTREAM_PORT) : inference 서버가 열려 있는 숫자 형태의 포트 데이터입니다. ex) 8090

APP_INFERENCE_NODE_ID=`<inference-node-id>`
>추론 노드 식별자(APP_INFERENCE_NODE_ID) : inference 서버를 구분하기 위한 문자열 형태의 노드 ID 데이터입니다. ex) infer-gpu-01

APP_INFERENCE_WS_BASE_URL=`<inference-websocket-base-path>`
>추론 웹소켓 경로(APP_INFERENCE_WS_BASE_URL) : inference 서버의 WebSocket 기본 경로 문자열 형태의 데이터입니다. ex) /ws/inference/apply

APP_INFERENCE_RTC_OFFER_URL=`<inference-rtc-offer-path>`
>RTC 오퍼 경로(APP_INFERENCE_RTC_OFFER_URL) : inference 서버의 RTC offer API 경로 문자열 형태의 데이터입니다. ex) /rtc/inference/offer

APP_INFERENCE_RTC_ICE_SERVERS_JSON=`<json-array-of-ice-servers>`
>ICE 서버 목록(APP_INFERENCE_RTC_ICE_SERVERS_JSON) : WebRTC용 STUN/TURN 서버 정보를 담은 JSON 배열 문자열 형태의 데이터입니다. ex) [{"urls":["stun:3.35.4.105:3478","turn:3.35.4.105:3478?transport=udp"],"username":"hairapply","credential":"hairapply-turn-secret"}]

APP_INFERENCE_METADATA_SYNC_SECRET=`<inference-metadata-sync-secret>`
>메타데이터 동기화 시크릿(APP_INFERENCE_METADATA_SYNC_SECRET) : inference와 backend 사이 내부 동기화 인증에 사용하는 문자열 형태의 데이터입니다. ex) hairapply-metadata-sync-secret-2026