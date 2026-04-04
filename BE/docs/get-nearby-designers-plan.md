# Nearby Designer 조회 기능 계획

작성일: 2026-03-31

## 1. 목적

사용자가 특정 헤어를 보고 `가까운 디자이너`를 조회하면,
해당 헤어 카테고리에 자신있다고 등록한 디자이너들만 추려서
현재 사용자 위치 기준 가까운 순으로 반환한다.

사용할 API 경로는 아래로 고정한다.

- `POST /api/camera/get-designer/`

## 2. 현재 전제

현재 백엔드에는 아래 구조가 이미 준비되어 있다.

- `hairs.category_id`
  - 헤어가 어떤 카테고리에 속하는지 저장
- `hair_categories`
  - 카테고리 원본 테이블
- `designer_specialties`
  - 디자이너가 자신있는 카테고리 저장
- `designer_applications`
  - 디자이너 신청 정보와 미용실 주소 저장
  - `salon_latitude`, `salon_longitude` 포함
- `users.grade`
  - `2`인 사용자만 승인된 디자이너

즉 이제는 `hair_id`를 실제 필터링에 사용할 수 있다.

## 3. 프론트 요청값

프론트는 아래 3개를 body로 전달한다.

- `hair_id`
- `latitude`
- `longitude`

요청 예시:

```json
{
  "hair_id": 5,
  "latitude": 37.503222148427824,
  "longitude": 127.02794220562396
}
```

설명:

- `hair_id`
  - 사용자가 보고 있는 헤어 ID
- `latitude`
  - 현재 사용자 위치 위도
- `longitude`
  - 현재 사용자 위치 경도

## 4. 조회 조건

조회 대상 디자이너는 아래 조건을 모두 만족해야 한다.

1. `hair_id`로 조회한 헤어가 존재한다.
2. 해당 헤어의 `category_id`가 존재한다.
3. `designer_specialties.category_id = hairs.category_id`
4. `users.grade = 2`
5. `designer_applications` 레코드가 존재한다.
6. `salon_latitude`, `salon_longitude`가 존재한다.

즉 단순히 디자이너 등급만 있다고 나오는 것이 아니라,
아래가 모두 있어야 한다.

- 승인된 디자이너
- 자신있는 헤어 카테고리 등록
- 디자이너 신청 정보 존재
- 미용실 좌표 존재

## 5. 최종 조회 흐름

권장 조회 흐름은 아래와 같다.

1. `hair_id`로 `hairs` 조회
2. 조회한 헤어의 `category_id` 확인
3. `designer_specialties`에서 해당 `category_id`를 가진 사용자 조회
4. `users.grade = 2` 조건으로 승인 디자이너만 남김
5. `designer_applications`에서 미용실 좌표 조회
6. 사용자 위치와 미용실 위치 거리 계산
7. 가까운 순으로 정렬
8. 응답 반환

## 6. 거리 계산 방식

발표용 1차 구현은 Java 서비스 레벨에서 거리 계산하는 것이 가장 단순하다.

권장 방식:

- Haversine 공식 사용

이유:

- 현재 데이터 수가 많지 않다.
- SQL을 복잡하게 만들 필요가 없다.
- 디버깅이 쉽다.

## 7. 응답 형태

발표용 응답은 아래 정도면 충분하다.

```json
{
  "code": 200,
  "message": "조회 정상",
  "designers": [
    {
      "userId": "designer01",
      "salonAddress": "서울특별시 강남구 ...",
      "distanceKm": 1.24,
      "latitude": 37.5012,
      "longitude": 127.0396
    },
    {
      "userId": "designer02",
      "salonAddress": "서울특별시 서초구 ...",
      "distanceKm": 2.87,
      "latitude": 37.4901,
      "longitude": 127.0221
    }
  ]
}
```

필수 응답 후보:

- `userId`
- `salonAddress`
- `distanceKm`
- `latitude`
- `longitude`

선택 응답 후보:

- `categoryId`
- `categoryName`

## 8. 예외 처리 정책

권장 정책은 아래와 같다.

### 1. `hair_id`가 존재하지 않음

- `404`
- 메시지: `헤어를 찾을 수 없습니다.`

### 2. `hair.category_id`가 비어 있음

- `400` 또는 `404`
- 권장: `400`
- 메시지: `헤어 카테고리 정보가 없습니다.`

### 3. 좌표 형식 오류

- `400`
- 메시지: `위치 정보가 올바르지 않습니다.`

### 4. 조건에 맞는 디자이너가 없음

- `200`
- `designers: []`

이 경우는 오류로 볼 필요가 없다.

## 9. API 인증

현재 서비스 전제를 유지하면 로그인 사용자 기준으로 처리하는 것이 자연스럽다.

권장:

- 인증 필요
- 쿠키 인증 사용자만 호출 가능

이유:

- 사용자 위치 정보가 포함된다.
- 이후 개인화 흐름과도 연결하기 쉽다.

## 10. 백엔드 구성 제안

### Controller

추가 또는 수정 대상:

- `api/CameraController`

추가 엔드포인트:

- `POST /api/camera/get-designer/`

### DTO

추가 대상:

- `api/dto/camera/GetNearbyDesignerRequest`
- `api/dto/camera/GetNearbyDesignerResponse`

요청 DTO:

- `hair_id`
- `latitude`
- `longitude`

응답 DTO:

- `designers`
  - `userId`
  - `salonAddress`
  - `distanceKm`
  - `latitude`
  - `longitude`

### Service

추가 대상:

- `service/NearbyDesignerService`

역할:

- 헤어 조회
- 카테고리 확인
- 디자이너 후보 조회
- 거리 계산
- 가까운 순 정렬
- 응답 DTO 변환

### Repository

추가 또는 확장 필요:

- `DesignerSpecialtyRepository`
  - `findAllByCategoryId(...)` 또는 유사 메서드 필요
- `DesignerApplicationRepository`
  - 후보 디자이너의 주소/좌표 조회 필요
- `UserAccountRepository` 또는 JPA repository
  - `grade = 2` 여부 확인 필요

## 11. 권장 구현 방식

발표용 기준으로는 아래 방식이 가장 단순하다.

1. `hair_id`로 헤어 1건 조회
2. 해당 `category_id`를 가진 specialty 사용자 목록 조회
3. 각 사용자에 대해:
   - `grade = 2` 확인
   - `designer_applications` 조회
   - 좌표가 있으면 거리 계산
4. 결과를 메모리에서 정렬 후 반환

즉 SQL 한 방으로 복잡하게 묶기보다,
서비스 레벨에서 조합하는 것이 구현 속도와 안정성 면에서 낫다.

## 12. 구현 순서

1. 요청/응답 DTO 추가
2. `DesignerSpecialtyRepository`에 카테고리 기준 조회 메서드 추가
3. `DesignerApplicationRepository`에 사용자별 신청 정보 조회 메서드 보강
4. `NearbyDesignerService` 구현
5. `CameraController`에 엔드포인트 추가
6. 통합 테스트 작성

## 13. 테스트 항목

최소 테스트 항목은 아래와 같다.

1. 인증 없이 호출 시 `401`
2. 존재하지 않는 `hair_id` 호출 시 `404`
3. 조건에 맞는 디자이너가 없으면 빈 배열 반환
4. 같은 카테고리의 디자이너만 반환
5. `grade = 2` 아닌 사용자는 제외
6. 거리순 정렬이 맞는지 확인

## 14. 발표용 1차 구현 범위

이번 단계에서는 아래까지만 구현하면 충분하다.

1. `hair_id -> category_id` 연결
2. `designer_specialties` 기반 카테고리 매칭
3. 승인된 디자이너만 필터링
4. 사용자 위치 기준 거리 계산
5. 가까운 순 정렬 응답

즉 1차 목표는:

- `헤어 카테고리가 맞는 디자이너`
- `그중 가까운 디자이너`

를 반환하는 것이다.

## 15. 결론

이제 `designer_specialties`와 `hairs.category_id`가 있으므로,
`/api/camera/get-designer/`는 단순 거리 추천이 아니라
실제 헤어 카테고리까지 반영한 디자이너 추천으로 구현할 수 있다.

권장 구현 방향은 아래와 같다.

- `hair_id`로 헤어 카테고리 확인
- 해당 카테고리를 specialty로 가진 디자이너만 추림
- `grade = 2`와 좌표 존재 여부까지 확인
- 사용자 위치와의 거리 기준으로 정렬해서 반환
