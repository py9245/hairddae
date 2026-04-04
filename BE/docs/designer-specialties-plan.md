# Designer Specialties 계획

작성일: 2026-03-31

## 1. 배경

다음 작업 목표는 디자이너로 승인된 사용자가 내정보에서 `자신있는 헤어`를 선택해서 저장할 수 있게 만드는 것이다.

현재 전제는 다음과 같다.

- 디자이너 여부는 `users.grade`로 구분
  - `0`: 일반 유저
  - `1`: 디자이너 신청자
  - `2`: 디자이너 승인자
- 헤어 카테고리는 정규화 작업을 통해 `hair_categories`를 기준으로 관리하기 시작함
- 이후 `/api/camera/get-designer/`에서 사용자가 선택한 헤어와 가까운 디자이너를 연결할 계획이 있음

## 2. 왜 `users` 컬럼 하나로 저장하지 않는가

처음에는 `users` 테이블에 자신있는 헤어 컬럼 하나를 추가하는 방법도 가능하다.

하지만 이 방식은 한계가 있다.

- 디자이너가 카테고리 하나만 선택할 수 있게 고정됨
- 나중에 여러 개 선택으로 확장하기 어려움
- 지금 막 정규화한 `hair_categories` 구조를 다시 문자열 컬럼으로 우회하게 됨

그래서 저장 위치는 `users` 단일 컬럼보다 별도 매핑 테이블이 더 적합하다.

## 3. 권장 구조

새 테이블 `designer_specialties`를 만든다.

권장 컬럼:

- `id BIGSERIAL PRIMARY KEY`
- `user_id VARCHAR(50) NOT NULL`
- `category_id VARCHAR(50) NOT NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

FK 권장:

- `user_id -> users.user_id`
- `category_id -> hair_categories.category_id`

유니크 제약 권장:

- `UNIQUE (user_id, category_id)`

이 구조를 쓰면:

- 한 디자이너가 여러 카테고리를 가질 수 있음
- 같은 카테고리를 중복 저장하지 않음
- `hair_categories`를 그대로 참조하게 됨

## 4. 저장 정책

저장 대상은 `grade = 2`인 사용자만 허용하는 것이 맞다.

즉:

- 일반 유저는 저장 불가
- 신청자(`grade = 1`)도 저장 불가
- 승인된 디자이너(`grade = 2`)만 저장 가능

## 5. API 방향

내정보 기준으로 아래 API 구성이 자연스럽다.

### 1. 카테고리 목록 조회

프론트는 이미 `/api/home/categorylist/`를 통해 카테고리 목록을 받을 수 있다.

즉 디자이너 전용 카테고리 목록 API를 따로 만들지 않고, 기존 카테고리 목록을 재사용해도 된다.

### 2. 디자이너 자신있는 헤어 저장

권장 URL:

- `POST /api/mypage/designer/specialties/`

요청 예시:

```json
{
  "categoryIds": ["가르마", "댄디컷", "리젠트컷"]
}
```

설명:

- 여러 개 선택을 허용하는 구조로 시작
- 프론트가 1개만 선택하게 하더라도 배열 구조가 나중 확장에 유리

### 3. 디자이너 자신있는 헤어 조회

권장 URL:

- `GET /api/mypage/designer/specialties/`

응답 예시:

```json
{
  "code": 200,
  "message": "조회 정상",
  "specialties": [
    {
      "categoryID": "가르마",
      "categoryName": "가르마"
    },
    {
      "categoryID": "댄디컷",
      "categoryName": "댄디컷"
    }
  ]
}
```

## 6. 저장 방식 권장안

저장 방식은 `replace` 방식이 제일 단순하다.

즉 `POST` 요청이 들어오면:

1. 현재 사용자 디자이너 여부 확인
2. 요청한 `categoryIds` 유효성 확인
3. 해당 사용자의 기존 specialties 삭제
4. 새 specialties 일괄 저장

장점:

- 프론트가 현재 선택 상태 전체를 그대로 보내면 됨
- 백엔드 로직이 단순함
- 발표용 구현에 적합

주의:

- 삭제 후 재삽입 방식이므로 트랜잭션 처리 필요

## 7. `/api/camera/get-designer/`와의 연결 방향

이후 가까운 디자이너 조회 API와 자연스럽게 연결할 수 있다.

예상 흐름:

1. 프론트가 `hair_id`, `latitude`, `longitude` 전송
2. 백엔드가 `hair_id`로 `hairs.category_id` 조회
3. `designer_specialties`에서 해당 `category_id`를 가진 디자이너 조회
4. 그중 `users.grade = 2`이고 좌표가 있는 디자이너만 남김
5. 거리순으로 정렬해서 반환

즉 이번 작업은 이후 디자이너 추천 기능의 기반이 된다.

## 8. 구현 순서 권장안

### 1단계. 스키마 추가

Flyway로 `designer_specialties` 테이블 생성

### 2단계. 엔티티/리포지토리 추가

필요 파일:

- `DesignerSpecialtyEntity`
- `DesignerSpecialtyJpaRepository`

### 3단계. DTO/서비스/컨트롤러 추가

필요 구성:

- 저장 요청 DTO
- 조회 응답 DTO
- `DesignerSpecialtyService`
- `DesignerSpecialtyController`

### 4단계. 검증 로직 추가

검증 항목:

- 로그인 사용자 여부
- `grade = 2` 여부
- 요청 카테고리 목록 비어 있지 않은지
- `hair_categories`에 실제 존재하는 category인지
- 중복 categoryId 제거

### 5단계. 테스트

테스트 항목:

- 디자이너만 저장 가능
- 일반 사용자 저장 불가
- 존재하지 않는 category 저장 불가
- 저장 후 조회 가능
- 중복 카테고리 요청 시 중복 저장되지 않음

## 9. 발표용 최소 구현 범위

발표 기준으로는 아래만 해도 충분하다.

1. `designer_specialties` 테이블 생성
2. `POST /api/mypage/designer/specialties/`
3. `GET /api/mypage/designer/specialties/`
4. `grade = 2` 사용자만 저장 가능
5. `/api/home/categorylist/`를 그대로 선택지로 사용

즉 1차 구현에서는:

- 디자이너가 자신있는 헤어를 등록할 수 있게 함
- 이후 `get-designer` 고도화 때 바로 사용할 수 있는 구조를 먼저 깔아둠

## 10. 결론

이번 기능은 `users`에 컬럼 하나를 추가하는 것보다, `designer_specialties` 매핑 테이블을 두는 것이 더 맞다.

이 방식의 장점은 다음과 같다.

- 다중 카테고리 선택 가능
- `hair_categories` 정규화 구조를 그대로 활용 가능
- 이후 디자이너 추천 API와 자연스럽게 연결 가능

따라서 권장 방향은:

- `designer_specialties` 테이블 추가
- 디자이너 전용 저장/조회 API 구현
- 이후 `hair_id -> category_id -> designer_specialties` 흐름으로 확장
