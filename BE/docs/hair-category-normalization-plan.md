# Hair Category 정규화 계획

작성일: 2026-03-31

## 1. 배경

현재 카테고리 데이터는 두 군데에 나뉘어 있다.

- `hairs.category`
  - 문자열 컬럼
  - 실제 헤어 데이터가 이 값을 직접 들고 있음
- `hair_categories`
  - 별도 테이블은 있지만 현재 데이터가 비어 있음

현재 `/api/home/categorylist/` 응답은 `hair_categories`를 기준으로 만들지 않고, 활성 헤어들의 `hairs.category` 값을 중복 제거해서 반환하고 있다.

즉 지금 구조는:

- `hairs.category`가 사실상 카테고리 원본 데이터
- `hair_categories`는 아직 메타데이터 테이블로만 존재

## 2. 현재 코드 기준 확인 사항

- `hairs.category`는 문자열 컬럼으로 저장됨
- `hair_categories`는 `category_id`, `category_name`, `preview_image_url`, `display_order`, `is_active` 등을 가짐
- `/api/home/categorylist/`는 현재 활성 헤어를 조회한 뒤 `category` 문자열을 중복 제거해서 응답함

현재 이 로직은 아래 코드 기준으로 확인됨.

- [V1__initial_schema.sql](/home/ubuntu/S14P21M101/BE/src/main/resources/db/migration/V1__initial_schema.sql)
- [V4__create_hair_categories.sql](/home/ubuntu/S14P21M101/BE/src/main/resources/db/migration/V4__create_hair_categories.sql)
- [HairEntity.java](/home/ubuntu/S14P21M101/BE/src/main/java/com/example/beapp/persistence/entity/HairEntity.java)
- [HairCategoryEntity.java](/home/ubuntu/S14P21M101/BE/src/main/java/com/example/beapp/persistence/entity/HairCategoryEntity.java)
- [HairCatalogService.java](/home/ubuntu/S14P21M101/BE/src/main/java/com/example/beapp/service/HairCatalogService.java)

## 3. 목표 구조

카테고리의 단일 원본은 `hair_categories`가 되도록 정리한다.

목표는 다음과 같다.

- 카테고리 정의는 `hair_categories`에서 관리
- `hairs`는 카테고리 문자열을 직접 들고 있지 않고 `hair_categories`를 참조
- `/api/home/categorylist/`도 더 이상 `hairs.category` 중복 제거 방식이 아니라 `hair_categories` 기준으로 응답

## 4. 권장 방식

직접 `hairs.category`를 바로 FK로 바꾸는 것보다, 단계적으로 이전하는 방식을 권장한다.

이유:

- 현재 운영 코드가 아직 `hairs.category`를 직접 읽고 있음
- 바로 rename/drop 하면 한 번의 배포에 스키마와 코드가 모두 정확히 맞아야 함
- Flyway와 JPA 검증을 함께 쓰고 있어서, 단계적 이전이 더 안전함

## 5. 단계별 전환 계획

### 1차. `hair_categories`에 기존 카테고리 이관

`hairs.category`의 distinct 값을 `hair_categories`에 채운다.

초기 이관 규칙:

- `hair_categories.category_id = hairs.category`
- `hair_categories.category_name = hairs.category`
- `is_active = true`
- `display_order = 0`
- `preview_image_url`, `description`은 일단 `null` 허용

의도:

- 현재 운영 중인 카테고리 문자열을 먼저 메타 테이블로 흡수
- 이후 사람이 `category_name`, `display_order`, `preview_image_url`를 정리할 수 있게 함

### 2차. `hairs`에 참조용 컬럼 추가

기존 `category`를 바로 없애지 말고, 먼저 참조용 컬럼을 추가한다.

권장안:

- `hairs.category_id VARCHAR(50)` 신규 추가
- 기존 `hairs.category` 값으로 `hairs.category_id` 백필
- `hairs.category_id -> hair_categories.category_id` FK 추가
- 인덱스 추가: `(category_id, is_active)`

이 단계에서는 기존 `category` 컬럼은 남겨둔다.

### 3차. 백엔드 코드 전환

코드가 `hairs.category` 대신 `hairs.category_id`를 보도록 변경한다.

영향 범위:

- `HairEntity`
- `HairJpaRepository`
- `HairCatalogService`
- `/api/home/categorylist/`
- 카테고리 필터가 들어가는 헤어 조회 API

전환 후 기준:

- `categorylist`
  - `hair_categories` 기준 조회
- `categorycardlist`, 헤어 목록
  - `hairs.category_id` 기준 필터링

### 4차. `/api/home/categorylist/` 응답 기준 정리

현재는 활성 헤어를 기준으로 카테고리를 노출한다.

이 동작은 유지하는 것이 안전하다.

즉 1차 구현에서는:

- `hair_categories` 전체를 다 보여주지 않고
- 활성 헤어가 하나 이상 연결된 카테고리만 응답

응답 값:

- `categoryID = hair_categories.category_id`
- `categoryName = hair_categories.category_name`
- `image`
  - 우선순위 1: `hair_categories.preview_image_url`
  - 우선순위 2: 해당 카테고리의 대표 헤어 preview

### 5차. 안정화 후 기존 `hairs.category` 제거

코드가 완전히 `category_id` 기준으로 전환된 뒤 마지막에 기존 문자열 컬럼을 제거한다.

최종 정리:

- 기존 `idx_hairs_category_active` 제거
- 기존 `hairs.category` 제거
- `hairs.category_id`를 `NOT NULL` 유지

## 6. 마이그레이션 권장 순서

권장 Flyway 순서:

1. `V10`
   - `hair_categories`에 distinct category 이관
2. `V11`
   - `hairs.category_id` 추가
   - 백필
   - FK/인덱스 추가
3. 코드 배포
   - `category_id` 기준으로 읽기 전환
4. `V12`
   - 기존 `hairs.category` 제거
   - 불필요 인덱스 제거

## 7. 데이터 이관 시 주의점

### 카테고리 명칭 중복

현재 `hairs.category` 값이 영문 ID인지, 한국어 이름인지 먼저 확인이 필요하다.

예:

- `short`
- `medium`
- `long`

또는

- `숏`
- `미디엄`
- `롱`

현재 값이 곧바로 사용자 노출용 문자열이 아니라면, 이관 후 `category_name`은 별도 정리가 필요하다.

### 비활성 헤어만 가진 카테고리

`hair_categories`에는 들어가더라도, `/api/home/categorylist/`에서 노출할지는 정책 결정이 필요하다.

권장:

- 테이블에는 유지
- 홈 카테고리 목록에서는 활성 헤어가 있는 것만 노출

### 미리보기 이미지

현재 `categorylist`는 사실상 첫 번째 헤어 이미지에 의존한다.

`hair_categories.preview_image_url`가 비어 있는 상태에서는, 기존처럼 대표 헤어 preview를 fallback으로 쓰는 편이 안전하다.

## 8. 1차 구현 범위 권장안

지금 당장 구현할 1차 범위는 아래로 권장한다.

1. `hairs.category` distinct 값을 `hair_categories`에 이관
2. `hairs.category_id` 신규 컬럼 추가 및 FK 연결
3. `/api/home/categorylist/`를 `hair_categories` 기준으로 전환
4. 기존 `hairs.category`는 당장은 유지

즉 1차에서는:

- 데이터 정규화 시작
- API 기준 전환
- 기존 컬럼 제거는 보류

이 방식이 가장 안전하다.

## 9. 구현 전 확인할 것

구현 전에 아래 두 가지를 먼저 확인하면 좋다.

1. 현재 `hairs.category` 실제 distinct 값 목록
2. 홈 카테고리 목록에서 비활성 카테고리를 보여줄지 여부

## 10. 결론

이번 작업은 단순히 `hair_categories`를 채우는 것에서 끝나지 않고, 카테고리 원본을 `hair_categories`로 옮기는 정규화 작업이다.

가장 안전한 방향은 다음이다.

- `hair_categories`를 먼저 채운다
- `hairs`에 참조 컬럼을 단계적으로 추가한다
- API를 `hair_categories` 기준으로 전환한다
- 마지막에 기존 `hairs.category`를 제거한다

즉, 직접 한 번에 바꾸기보다 `데이터 이관 -> 참조 연결 -> 코드 전환 -> 기존 컬럼 제거` 순서가 맞다.
