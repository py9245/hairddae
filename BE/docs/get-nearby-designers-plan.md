# Nearby Designer 조회 기능 계획

작성일: 2026-03-31

## 목적

사용자가 헤어 적용 후 `가까운 디자이너`를 조회하면,
사용자 위치와 디자이너 미용실 위치를 기준으로
가까운 디자이너 목록을 반환하는 기능을 만든다.

이번 단계에서는 아래를 기준으로 구현한다.

- 디자이너 여부는 `users.grade = 2` 로 판단
- 디자이너 위치는 `디자이너 신청 시 입력한 salonAddress` 기준
- `salonAddress` 는 신청 시 좌표로 변환해 DB에 저장
- 조회 API 는 `/api/camera/get-designer/` 사용

## 기본 방향

디자이너 좌표는 조회 시마다 주소를 다시 변환하지 않고,
신청 시점에 한 번 변환해서 저장하는 방향이 맞다.

이유는 아래와 같다.

- 조회 속도가 빨라진다.
- 외부 주소 변환 API 호출을 줄일 수 있다.
- 발표 중 네트워크 변수에 덜 흔들린다.
- 거리 계산이 단순해진다.

즉 흐름은 아래처럼 간다.

1. 디자이너 신청 시 `salonAddress` 입력
2. 백엔드가 주소를 좌표로 변환
3. `designer_applications` 에 위도/경도 저장
4. 디자이너 조회 시 사용자 위치와 저장된 좌표를 비교
5. 가까운 순으로 반환

## 필요한 데이터

현재 `designer_applications` 에는 아래 정보가 있다.

- `user_id`
- `certificate_number`
- `salon_address`

가까운 디자이너 조회를 위해 아래 컬럼을 추가하는 것을 권장한다.

- `salon_latitude DOUBLE PRECISION`
- `salon_longitude DOUBLE PRECISION`

이 두 값은 신청 시 `salonAddress` 를 기준으로 저장한다.

## grade 기준

디자이너 조회 대상은 아래 조건을 만족해야 한다.

- `users.grade = 2`

즉 신청만 한 사용자 `grade = 1` 은 조회 대상이 아니다.

정리:

- `grade = 1`
  - 신청자
- `grade = 2`
  - 실제 디자이너 조회 대상

## 디자이너 조회 API

이번 단계에서는 아래 경로를 사용한다.

- `POST /api/camera/get-designer/`

이유:

- 사용자 위치 정보가 body 로 들어오므로 `POST` 가 단순하다.
- 현재 카메라/헤어 적용 흐름과도 연결하기 쉽다.

## 프론트 요청값

프론트에서는 아래 정보를 전달한다.

- `hair_id`
- `latitude`
- `longitude`

요청 예시:

```json
{
  "latitude": 37.5012,
  "longitude": 127.0396,
  "hair_id": 12
}
```

## hairId 처리 방향

현재 단계에서는 `hair_id` 는 받되, 실제 필터링에는 바로 사용하지 않는 것을 권장한다.

이유는 아래와 같다.

- 현재 DB에는 디자이너와 헤어스타일 간 매핑 정보가 없다.
- 따라서 `hair_id` 로 디자이너를 걸러낼 기준이 아직 없다.

즉 1차에서는:

- `hair_id` 는 요청값으로 받음
- 필요하면 존재 여부만 검증
- 실제 추천 기준은 거리 중심으로 처리

나중에 확장하려면 아래 같은 테이블이 필요하다.

- `designer_hair_specialties`

하지만 발표용 범위에서는 여기까지 갈 필요는 없다.

## 조회 대상 조건

가까운 디자이너 조회 대상은 아래 조건을 만족해야 한다.

- `users.grade = 2`
- `designer_applications` 레코드가 존재
- `salon_latitude IS NOT NULL`
- `salon_longitude IS NOT NULL`

즉 네가 DB에서 `grade = 2` 로 바꾼 사용자라도,
`designer_applications` 정보가 없거나 좌표가 없으면 조회할 수 없다.

## 거리 계산 방식

거리 계산은 1차에서는 Java 서비스 레벨에서 처리하는 것이 가장 단순하다.

권장 방식:

- Haversine 공식 사용

처리 흐름:

1. `grade = 2` 인 디자이너 후보 조회
2. 각 디자이너의 미용실 좌표와 사용자 좌표 거리 계산
3. 가까운 순으로 정렬
4. 상위 N명 반환

발표용 기준이면 이 방식으로 충분하다.

## 응답 예시

```json
{
  "code": 200,
  "message": "조회 정상",
  "designers": [
    {
      "userId": "designer01",
      "salonAddress": "서울특별시 강남구 ...",
      "distanceKm": 1.2
    },
    {
      "userId": "designer02",
      "salonAddress": "서울특별시 서초구 ...",
      "distanceKm": 2.8
    }
  ]
}
```

필요하면 아래도 추가 가능하다.

- `certificateNumber`
- `grade`

하지만 발표용이면 `userId`, `salonAddress`, `distanceKm` 정도면 충분하다.

## 백엔드 구성 제안

### Migration

새 Flyway 마이그레이션 추가:

- 예: `V8__add_designer_coordinates.sql`

추가 컬럼:

- `salon_latitude DOUBLE PRECISION`
- `salon_longitude DOUBLE PRECISION`

### Entity

수정 대상:

- `persistence/entity/DesignerApplicationEntity`

추가 필드:

- `salonLatitude`
- `salonLongitude`

### 신청 저장 로직

수정 대상:

- `service/DesignerApplicationService`

추가 역할:

- `salonAddress` -> 좌표 변환
- 좌표까지 같이 저장

### 조회 API

추가 대상:

- `api/CameraController`
  - 또는 별도 컨트롤러
- `service/NearbyDesignerService`
- `api/dto/camera/GetNearbyDesignerRequest`
- `api/dto/camera/GetNearbyDesignerResponse`

## 주소 -> 좌표 변환

이 기능의 핵심은 주소를 좌표로 바꾸는 지오코딩이다.

이 부분은 별도 외부 API가 필요하다.

즉 실제 구현 전 아래를 먼저 정해야 한다.

- 어떤 주소 변환 API를 쓸지
- 인증 키는 무엇인지
- 서버 환경변수로 어떻게 넣을지

현재 단계에서는 기능 계획만 먼저 잡고,
구현 직전 외부 API를 확정하는 것이 맞다.

## 발표용 운영 주의사항

발표 전에 `grade = 2` 로 바꿔둘 계정은 아래 조건을 만족해야 한다.

- `designer_applications` 레코드 존재
- `salonAddress` 존재
- 좌표 저장 완료

즉 단순히 `users.grade = 2` 만 바꾸는 것으로는 부족하다.
디자이너 신청 데이터와 좌표까지 있어야 조회 결과에 포함된다.

## 구현 순서 제안

1. `designer_applications` 에 좌표 컬럼 추가
2. 신청 시 주소를 좌표로 변환해 저장
3. 기존 디자이너 신청 데이터 좌표 백필
4. `/api/camera/get-designer/` API 추가
5. 거리 계산 및 가까운 순 정렬 구현
6. 응답 반환 및 최소 테스트 추가

## 권장 결론

이번 기능은 아래 기준으로 구현하는 것이 가장 자연스럽다.

- 디자이너 위치는 `salonAddress` 기준
- 주소는 신청 시 한 번 좌표로 변환해서 저장
- 조회 시 `users.grade = 2` 인 사용자만 대상
- 사용자 위치와 디자이너 좌표의 거리로 정렬
- `hair_id` 는 1차에서는 받기만 하고 거리 조회 중심으로 사용
