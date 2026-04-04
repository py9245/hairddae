# Designer 신청 기능 계획

작성일: 2026-03-31

## 목적

발표용 데모 기준으로, 로그인한 사용자가 마이페이지에서 `디자이너 신청`을 하면
`certificateNumber`, `salonAddress`, `acquisitionDate` 를 저장하고,
사용자 등급을 통해 일반 사용자와 디자이너를 구분할 수 있게 한다.

이번 단계에서는 복잡한 승인 시스템이나 관리자 화면은 만들지 않는다.

## 기본 방향

구조는 아주 단순하게 간다.

- `users.grade` 추가
- `designer_applications` 테이블 추가
- 신청 API는 1개만 구현
- 승인 처리는 발표 전후로 DB에서 직접 변경

즉,

- `users.grade`
  - 현재 사용자 상태 확인용
- `designer_applications`
  - 신청 시 입력한 자격증 번호, 발급 일자, 미용실 주소, 미용실 좌표 저장용

## grade 정의

`users.grade` 는 아래처럼 사용한다.

- `0`: 일반 사용자
- `1`: 디자이너 신청자
- `2`: 디자이너

권장 타입:

- `SMALLINT NOT NULL DEFAULT 0`

권장 제약:

- `CHECK (grade IN (0, 1, 2))`

## 테이블 설계

### users

기존 `users` 테이블에 아래 컬럼만 추가한다.

- `grade SMALLINT NOT NULL DEFAULT 0`

### designer_applications

발표용 최소 구조는 아래 정도면 충분하다.

- `id BIGSERIAL PRIMARY KEY`
- `user_id VARCHAR(50) NOT NULL`
- `certificate_number VARCHAR(255) NOT NULL`
- `acquisition_date DATE NULL`
- `salon_address VARCHAR(500) NOT NULL`
- `salon_latitude DOUBLE PRECISION NULL`
- `salon_longitude DOUBLE PRECISION NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

권장 제약:

- `FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE`
- `UNIQUE (user_id)`

설명:

- `certificate_number`
  - 신청 모달에서 입력한 자격증 라이선스
- `acquisition_date`
  - 신청 모달에서 입력한 발급 일자
- `salon_address`
  - 신청 모달에서 입력한 미용실 주소
- `salon_latitude`, `salon_longitude`
  - 미용실 주소를 좌표로 변환한 값

중요:

- 프론트엔드 요청 필드는 `certificateNumber`, `salonAddress`, `acquisitionDate` 를 사용한다.
- DB 컬럼명은 `certificate_number`, `salon_address`, `acquisition_date` 로 저장한다.
- 백엔드는 `salonAddress` 를 좌표로 변환해 `salon_latitude`, `salon_longitude` 도 함께 저장한다.

## 왜 별도 테이블을 두는가

`users` 에 라이선스 번호와 미용실 주소를 바로 넣지 않고
`designer_applications` 를 따로 두는 이유는 단순하다.

- 사용자 기본 정보와 신청 정보를 분리할 수 있다.
- 발표 후 확장할 때 덜 깨진다.
- 신청 정보 조회가 쉬워진다.

## 1차 처리 흐름

1. 로그인 사용자가 디자이너 신청 모달 오픈
2. `certificateNumber`, `salonAddress`, `acquisitionDate` 입력
3. `POST /api/mypage/designer/` 호출
4. 백엔드가 `salonAddress` 를 위도/경도로 변환
5. `designer_applications` 에 신청 정보와 좌표 저장
5. `users.grade = 1` 로 변경
6. 발표용 운영에서는 필요한 계정을 DB에서 직접 `grade = 2` 로 변경

## 발표용 승인 방식

이번 단계에서는 관리자 승인 API를 만들지 않는다.

발표용 운영 방식은 아래처럼 단순하게 간다.

- 신청 완료 사용자
  - `users.grade = 1`
- 디자이너로 보여주고 싶은 사용자
  - DB에서 직접 `users.grade = 2`

필요하면 신청 정보는 `designer_applications` 에 남겨두고 조회만 한다.

## API 제안

1차는 아래 API 하나만 있으면 된다.

- `POST /api/mypage/designer/`

인증:

- 로그인 사용자만 호출 가능

요청 예시:

```json
{
  "certificateNumber": "1234-5678-ABCD",
  "salonAddress": "서울특별시 강남구 ...",
  "acquisitionDate": "2024-01-15"
}
```

응답 예시:

```json
{
  "code": 200,
  "message": "디자이너 신청이 완료되었습니다.",
  "success": true
}
```

## 중복 신청 정책

프론트엔드에서 `신청 후 승인/거절 전까지 재신청 불가`로 막는 방향은 발표용으로 충분히 괜찮다.

다만 백엔드도 최소한의 방어는 두는 게 낫다.

권장 최소 방어:

- `designer_applications.user_id UNIQUE`
- 이미 신청 레코드가 있으면 신청 API에서 중복 저장 거절

이유:

- FE 차단만 믿으면 직접 API 호출 시 중복 데이터가 생길 수 있다.
- `UNIQUE` 하나만 있어도 발표용 기준에서는 충분히 깔끔하다.

즉 정리하면:

- 사용자 경험 차단은 `FE`
- 데이터 무결성 최소 보장은 `BE`

이 조합이 가장 단순하고 안전하다.

## 반려 처리

이번 단계에서는 반려 이력까지 만들지 않는다.

만약 발표 중 반려 상태를 보여줘야 하면 아주 단순하게 처리한다.

- `users.grade = 0`
- 필요 시 `designer_applications` 레코드 삭제

이렇게 하면 다시 신청 가능 상태로 되돌릴 수 있다.

## 백엔드 구성 제안

### Migration

Flyway 마이그레이션으로 처리한다.

- 예: `V7__add_user_grade_and_designer_applications.sql`

주의:

- PostgreSQL 프로그램에서 직접 스키마를 수정하지 않는다.
- 실제 변경은 Flyway 파일로 넣는다.

### Entity

- `persistence/entity/UserEntity`
  - `grade` 필드 추가
- `persistence/entity/DesignerApplicationEntity`
  - 신규 생성

### Repository

- `persistence/repository/UserJpaRepository`
- `persistence/repository/DesignerApplicationJpaRepository`

### Service

- `service/DesignerApplicationService`

역할:

- 현재 로그인 사용자 식별
- 중복 신청 여부 확인
- 신청 정보 저장
- 사용자 grade 변경

### Controller

- `api/DesignerApplicationController`

### DTO

- `api/dto/designer/DesignerApplicationRequest`
- `api/dto/designer/DesignerApplicationResponse`

DTO 요청 필드도 프론트와 동일하게 아래 이름으로 받는 것을 권장한다.

- `certificateNumber`
- `salonAddress`
- `acquisitionDate`

백엔드는 요청으로 받은 `salonAddress` 를 기준으로
위도/경도를 구해서 함께 저장하는 방식으로 구현한다.

## 보안/권한 범위

이번 단계에서는 보안을 과하게 확장하지 않는다.

현재 목표는 아래 정도다.

- 신청 API는 로그인 사용자만 호출 가능
- 디자이너 여부는 `users.grade` 로만 구분
- 관리자 권한 체계는 이번 범위에서 제외

## 구현 순서

1. Flyway 마이그레이션 추가
2. `UserEntity` 에 `grade` 필드 추가
3. `DesignerApplicationEntity` / Repository 추가
4. 신청 DTO / Service / Controller 추가
5. SecurityConfig 에 신청 API 인증 경로 추가
6. 최소 테스트 추가

## 권장 결론

발표용 기준으로는 아래 구조가 가장 단순하고 충분하다.

- `users.grade` 추가
- `designer_applications` 테이블 추가
- 신청 시 `certificateNumber`, `salonAddress`, `acquisitionDate` 저장
- 신청 시 미용실 좌표도 함께 저장
- 신청 완료 시 `users.grade = 1`
- 발표용 디자이너 계정은 DB에서 직접 `users.grade = 2` 로 변경
- 중복 신청은 FE에서 막고, BE는 `UNIQUE(user_id)` 로 최소 방어
