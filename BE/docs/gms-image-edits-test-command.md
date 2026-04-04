# GMS `images/edits` 테스트 명령어

## 목적

백엔드 밖에서 `GMS` 자체가 정상 응답하는지 직접 확인할 때 쓰는 명령어다.

## 1. 환경변수 읽기

`BE` 루트에서 실행:

```bash
cd /home/ubuntu/S14P21M101/BE

GMS_BASE_URL=$(sed -n 's/^GMS_BASE_URL=//p' .env)
GMS_KEY=$(sed -n 's/^GMS_KEY=//p' .env)
GMS_IMAGE_MODEL=$(sed -n 's/^GMS_IMAGE_MODEL=//p' .env)
```

확인:

```bash
echo "$GMS_BASE_URL"
echo "$GMS_IMAGE_MODEL"
echo "$GMS_KEY" | cut -c1-12
```

## 2. 실제 이미지 파일 확인

예시:

```bash
ls -l /home/ubuntu/test.png
```

중요:

- `@/path/to/test.png` 같은 예시 경로를 그대로 쓰면 안 된다.
- 반드시 실제 존재하는 파일 경로로 바꿔야 한다.

## 3. 최소 `images/edits` 테스트

```bash
curl -sS "$GMS_BASE_URL/images/edits" \
  -H "Authorization: Bearer $GMS_KEY" \
  -F "model=$GMS_IMAGE_MODEL" \
  -F "prompt=헤어 영역은 자연스럽게 보정하고 현재 헤어스타일은 유지하며 눈썹 아래는 수정하지 마세요." \
  -F "image=@/home/ubuntu/test.jpg;type=image/jpeg"
```

## 4. 백엔드와 비슷한 옵션으로 테스트

```bash
curl -sS "$GMS_BASE_URL/images/edits" \
  -H "Authorization: Bearer $GMS_KEY" \
  -F "model=$GMS_IMAGE_MODEL" \
  -F "prompt=헤어 영역은 자연스럽게 보정하되 현재 이미지에 보이는 헤어스타일은 유지하세요. 눈썹 아래 영역은 수정하지 마세요. 눈, 코, 입, 피부, 얼굴형은 변경하지 마세요. 원본 인물의 동일성을 유지하고 배경과 의상도 변경하지 마세요. 전체 이미지는 자연스럽고 선명하게 정리해 주세요." \
  -F "n=1" \
  -F "size=1024x1024" \
  -F "quality=low" \
  -F "output_format=png" \
  -F "image=@/home/ubuntu/gms-test.jpg;type=image/jpeg"
```

## 5. 응답 저장해서 보기

```bash
curl -sS "$GMS_BASE_URL/images/edits" \
  -H "Authorization: Bearer $GMS_KEY" \
  -F "model=$GMS_IMAGE_MODEL" \
  -F "prompt=헤어 영역은 자연스럽게 보정하고 현재 헤어스타일은 유지하며 눈썹 아래는 수정하지 마세요." \
  -F "image=@/home/ubuntu/gms-test.jpg;type=image/jpeg" \
  -o /tmp/gms-response.json

cat /tmp/gms-response.json
```

## 6. 자주 나는 오류

### `GMS key not found in request`

원인:

- 현재 셸에 `$GMS_KEY`가 안 잡힘

확인:

```bash
echo "$GMS_KEY"
```

### `curl: (26) Failed to open/read local data from file/application`

원인:

- `image=@...` 뒤의 파일 경로가 틀림

확인:

```bash
ls -l /실제/이미지/경로.jpg
```

### `status=400`

원인 후보:

- `images/edits` 파라미터 조합 문제
- 이미지 파일 자체 문제
- GMS safety 정책 차단

이 경우에는 먼저 `3. 최소 images/edits 테스트`부터 성공시키는 게 맞다.
