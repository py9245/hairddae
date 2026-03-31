# Naver Geocoding 테스트 명령

작성일: 2026-03-31

## 1. 환경변수 확인

먼저 현재 셸에 네이버 키가 잡혀 있는지 확인한다.

```bash
echo "$X_NCP_APIGW_API_KEY_ID"
echo "$X_NCP_APIGW_API_KEY"
echo "$NAVER_GEOCODING_BASE_URL"
```

값이 비어 있으면 `.env`를 현재 셸에 로드한다.

```bash
cd /home/ubuntu/S14P21M101/BE
set -a
source .env
set +a
```

공식 문서 기준 Geocoding 호스트는 아래와 같다.

```env
NAVER_GEOCODING_BASE_URL=https://maps.apigw.ntruss.com
```

## 2. Geocoding curl 테스트

아래 명령으로 네이버 Geocoding API를 직접 호출한다.

```bash
curl -G "$NAVER_GEOCODING_BASE_URL/map-geocode/v2/geocode" \
  -H "X-NCP-APIGW-API-KEY-ID: $X_NCP_APIGW_API_KEY_ID" \
  -H "X-NCP-APIGW-API-KEY: $X_NCP_APIGW_API_KEY" \
  -H "Accept: application/json" \
  --data-urlencode "query=서울특별시 강남구 테헤란로 1"
```

## 3. 정상 응답 예시

```json
{
  "status": "OK",
  "addresses": [
    {
      "x": "127.0276100",
      "y": "37.4981000"
    }
  ]
}
```

설명:

- `x`: 경도
- `y`: 위도

## 4. 결과 해석

- `200`
  - 키와 서비스 설정은 정상
- `401`
  - 키가 잘못됐거나 `KEY ID / KEY` 매핑이 틀렸을 가능성 높음
- `403`
  - 서비스 사용 권한 또는 앱 설정 문제 가능성 높음
- `210`
  - `A subscription to the API is required`
  - Maps 서비스 구독 또는 Geocoding API 선택이 안 된 상태일 가능성 높음
- `230`
  - `Forbidden`
  - 앱 권한 또는 잘못된 애플리케이션 사용 가능성 높음
- `200` 이지만 `addresses` 가 비어 있음
  - 주소 해석 실패

## 5. 점검 포인트

- `X_NCP_APIGW_API_KEY_ID` 는 `Client ID` 여야 한다.
- `X_NCP_APIGW_API_KEY` 는 `Client Secret` 이어야 한다.
- 두 값은 같은 애플리케이션의 인증 정보여야 한다.
- `NAVER_GEOCODING_BASE_URL` 은 `https://maps.apigw.ntruss.com` 이어야 한다.
- 네이버 Cloud Platform에서 `Maps` 서비스 구독과 `Geocoding API` 선택이 모두 되어 있어야 한다.
