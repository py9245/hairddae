# 디자이너 1:1 채팅 기능 계획

## 목적

사용자가 원하는 헤어스타일을 적용하고 디자이너 리스트를 본 뒤, 특정 디자이너를 선택하면 1:1 채팅 화면으로 진입할 수 있게 한다.

추가 전제:

- 채팅 시작 시점에 사용자가 헤어스타일을 적용한 사진을 디자이너에게 먼저 전달한다.
- 즉, 채팅방은 텍스트만 오가는 구조가 아니라 `초기 이미지 + 이후 텍스트 메시지` 구조를 가진다.

현재 기준 전제는 아래와 같다.

- 사용자는 로그인 상태이며 쿠키 인증이 완료되어 있다.
- 디자이너 찾기 API는 이미 구현되어 있다.
- 사용자는 `/api/camera/get-designer/` 응답에서 디자이너 `userId`를 받는다.
- 발표용 범위이므로, 지나치게 복잡한 실시간 구조보다는 안정적인 구조가 우선이다.

---

## 통신 방식 비교

### 1. 단순 폴링

개념:

- FE가 일정 주기마다 새 메시지가 있는지 `GET` 요청을 보낸다.

장점:

- 구현이 가장 단순하다.
- Spring MVC 구조에서 바로 붙이기 쉽다.
- 디버깅이 쉽다.
- 발표용 MVP에 가장 안정적이다.

단점:

- 새 메시지가 없어도 계속 요청이 나간다.
- 실시간성이 아주 좋지는 않다.
- 폴링 주기가 짧으면 서버 요청 수가 늘어난다.

추천 상황:

- 1차 발표용
- 채팅방 수가 적음
- 빠르게 붙이고 싶음

### 2. 롱 폴링

개념:

- FE가 요청을 보내고, 서버는 새 메시지가 생기거나 타임아웃이 될 때까지 응답을 잠시 붙잡는다.

장점:

- 단순 폴링보다 실시간성이 좋다.
- 불필요한 빈 응답이 줄어든다.

단점:

- 구현 복잡도가 올라간다.
- 요청 대기 상태 관리가 필요하다.
- 타임아웃, 연결 종료, 재연결 처리까지 생각해야 한다.
- 발표용 범위에서는 복잡도 대비 이점이 크지 않을 수 있다.

추천 상황:

- 폴링보다 더 자연스러운 채팅 느낌이 필요함
- 하지만 WebSocket, SSE까지는 가고 싶지 않음

### 결론

1차 구현은 `단순 폴링`이 가장 적절하다.

이유:

- 이미 백엔드 구조가 REST 중심이다.
- 발표용으로는 안정성이 더 중요하다.
- 채팅 사용량이 많지 않을 가능성이 높다.
- 문제 발생 시 원인 추적이 쉽다.

추후 개선이 필요하면 `롱 폴링` 또는 `SSE`로 확장할 수 있다.

---

## 권장 구조

### 1. 채팅방

사용자와 디자이너가 1:1로 대화하는 단일 채팅방이 필요하다.

권장 정책:

- 일반 사용자 1명 + 디자이너 1명 = 채팅방 1개
- 같은 사용자와 같은 디자이너 조합이면 기존 채팅방 재사용

즉, 발표용 1차는 `(customer_user_id, designer_user_id)` 조합을 유니크하게 관리하는 것이 가장 단순하다.

`hair_id`는 채팅방 키에 넣지 않고, 필요하면 방 메타데이터로만 저장하는 방향이 낫다.

이유:

- 같은 디자이너와 여러 번 상담해도 채팅방이 계속 늘어나지 않는다.
- 목록 조회가 단순해진다.
- 현재 목적은 "디자이너와 연결"이지, 헤어별 방 분리가 핵심은 아니다.

다만 이번 요구사항에서는 채팅 시작 시점에 사용자가 적용 사진을 보내므로, 채팅방 생성 API에서:

- 디자이너 선택
- 헤어 적용 사진 업로드
- 첫 메시지(선택)

를 한 번에 받는 흐름이 가장 자연스럽다.

---

## DB 설계 초안

### 1. chat_rooms

역할:

- 사용자와 디자이너의 1:1 채팅방

권장 컬럼:

- `id BIGSERIAL PRIMARY KEY`
- `customer_user_id VARCHAR(50) NOT NULL`
- `designer_user_id VARCHAR(50) NOT NULL`
- `source_hair_id BIGINT NULL`
- `initial_image_url VARCHAR(500) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`

제약:

- `UNIQUE (customer_user_id, designer_user_id)`
- `customer_user_id -> users.user_id`
- `designer_user_id -> users.user_id`
- `source_hair_id -> hairs.id`

### 2. chat_messages

역할:

- 채팅방에 쌓이는 실제 메시지

권장 컬럼:

- `id BIGSERIAL PRIMARY KEY`
- `room_id BIGINT NOT NULL`
- `sender_user_id VARCHAR(50) NOT NULL`
- `message_type VARCHAR(20) NOT NULL`
- `message_text TEXT NULL`
- `image_url VARCHAR(500) NULL`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `read_at TIMESTAMPTZ NULL`

제약:

- `room_id -> chat_rooms.id`
- `sender_user_id -> users.user_id`

권장 인덱스:

- `chat_messages(room_id, id ASC)`
- `chat_rooms(customer_user_id, updated_at DESC)`
- `chat_rooms(designer_user_id, updated_at DESC)`

권장 메시지 타입:

- `TEXT`
- `IMAGE`

1차 구현에서는 이미지도 "메시지 1개"로 저장하는 방식이 가장 단순하다.

즉, 사용자가 채팅을 시작할 때 업로드한 적용 사진은:

- `chat_rooms.initial_image_url`에도 보관 가능
- 또는 `chat_messages`의 첫 번째 `IMAGE` 메시지로만 저장 가능

내 권장안은 `chat_messages`의 첫 번째 `IMAGE` 메시지로만 저장하는 방식이다.

이유:

- 채팅 히스토리와 데이터 구조가 일관된다.
- 나중에 이미지 메시지를 추가로 지원할 때도 그대로 확장 가능하다.
- `chat_rooms.initial_image_url` 같은 중복 데이터가 줄어든다.

따라서 실구현 시에는 `chat_rooms.initial_image_url`은 굳이 넣지 않고, 첫 메시지를 `IMAGE`로 저장하는 방향이 더 낫다.

---

## API 설계 초안

### 1. 채팅방 생성 또는 조회

`POST /api/chat/rooms/`

권장 요청 형식:

- `multipart/form-data`

이유:

- FE가 가지고 있는 헤어 적용 이미지를 그대로 보낼 수 있다.
- 이미지와 텍스트를 동시에 받기 쉽다.

요청 필드:

- `designer_user_id`
- `hair_id`
- `applied_image`
- `initial_message` (선택)

예시:

```text
designer_user_id=godam_eunsu
hair_id=5
applied_image=<file>
initial_message=이 스타일 상담 가능할까요?
```

동작:

- 현재 로그인 사용자 확인
- `designer_user_id`가 실제 `grade = 2` 인지 검증
- `(customer_user_id, designer_user_id)` 채팅방이 이미 있으면 기존 방 반환
- 없으면 새 방 생성
- 업로드 이미지를 정적 파일 경로에 저장
- 첫 `IMAGE` 메시지를 생성
- `initial_message`가 있으면 이어서 `TEXT` 메시지도 생성

응답:

```json
{
  "code": 200,
  "message": "채팅방 조회 성공",
  "room_id": 12,
  "designer_user_id": "godam_eunsu",
  "initial_image_url": "/static/chat/12/messages/1.png"
}
```

### 2. 메시지 전송

`POST /api/chat/rooms/{roomId}/messages/`

1차는 텍스트 메시지만 지원해도 충분하다.

요청:

```json
{
  "message_text": "이 헤어스타일 상담 가능할까요?"
}
```

동작:

- 현재 사용자가 해당 방 참여자인지 검증
- 메시지 저장
- `chat_rooms.updated_at` 갱신

### 3. 메시지 목록 조회

`GET /api/chat/rooms/{roomId}/messages/?after_id=120`

개념:

- 최초 진입 시 전체 또는 최근 N개 조회
- 이후에는 `after_id`보다 큰 메시지만 조회

응답:

```json
{
  "code": 200,
  "message": "메시지 조회 성공",
  "room_id": 12,
  "messages": [
    {
      "id": 121,
      "sender_user_id": "godam_eunsu",
      "message_type": "TEXT",
      "message_text": "네 가능합니다.",
      "image_url": null,
      "created_at": "2026-03-31T18:00:00Z",
      "mine": false
    },
    {
      "id": 120,
      "sender_user_id": "TestUser01",
      "message_type": "IMAGE",
      "message_text": null,
      "image_url": "/static/chat/12/messages/1.png",
      "created_at": "2026-03-31T17:59:00Z",
      "mine": true
    }
  ]
}
```

### 4. 채팅방 목록 조회

`GET /api/chat/rooms/`

역할:

- 내 채팅방 목록 조회
- 사용자/디자이너 모두 사용 가능

응답에는 아래 정도가 있으면 충분하다.

- `room_id`
- 상대방 `user_id`
- 마지막 메시지
- 마지막 메시지 시각

---

## 폴링 방식 설계

### 1차 권장안

단순 폴링으로 간다.

FE 동작:

1. 채팅방 진입 시 최근 메시지 조회
2. 이후 2초 또는 3초마다 `GET /api/chat/rooms/{roomId}/messages/?after_id=...`
3. 새 메시지가 있으면 화면 갱신

권장 주기:

- 활성 채팅 화면: 2초
- 비활성 화면 또는 목록 화면: 5초 이상 또는 폴링 중단

### 왜 롱 폴링이 아닌가

- 발표용에서는 구현 복잡도 대비 이점이 크지 않다.
- 지금 필요한 건 "안정적으로 채팅이 된다"는 시연이다.
- 단순 폴링이면 테스트와 장애 대응이 쉽다.

---

## 권한 및 검증

### 공통

- 모든 채팅 API는 인증 필요
- 현재 로그인 사용자가 해당 채팅방 참여자인지 검증

### 방 생성 시

- 대상 디자이너가 실제 `users.grade = 2` 인지 확인
- 자기 자신과 채팅방 생성 금지
- `applied_image`는 필수로 두는 것이 자연스럽다.
- 이미지 MIME/type, 최대 크기 검증 필요

### 메시지 전송 시

- 빈 문자열 금지
- 최대 길이 제한 필요
  - 예: `1000자`

---

## 1차 구현 범위

발표용으로는 아래까지만 구현하면 충분하다.

1. `chat_rooms`, `chat_messages` 테이블 추가
2. `POST /api/chat/rooms/`
3. 채팅 시작 시 `applied_image`를 첫 `IMAGE` 메시지로 저장
4. `GET /api/chat/rooms/`
5. `GET /api/chat/rooms/{roomId}/messages/`
6. `POST /api/chat/rooms/{roomId}/messages/`
7. FE는 단순 폴링 적용

이번 단계에서는 아래는 제외 가능하다.

- 읽음 처리 고도화
- 이미지 메시지
- 파일 첨부
- 롱 폴링
- SSE
- WebSocket

---

## 구현 순서 제안

1. Flyway migration으로 `chat_rooms`, `chat_messages` 추가
2. 엔티티/리포지토리 추가
3. 채팅방 생성 API 구현
4. 메시지 저장/조회 API 구현
5. 채팅방 목록 API 구현
6. 테스트 추가
7. FE는 단순 폴링으로 연결

---

## 최종 권장안

발표용 1차는 아래 조합이 가장 적절하다.

- 저장 구조: `chat_rooms` + `chat_messages`
- 채팅방 정책: 사용자 1명 + 디자이너 1명 당 1개 방
- 채팅 시작 시 헤어 적용 사진을 첫 `IMAGE` 메시지로 저장
- 통신 방식: `단순 폴링`
- 향후 확장: 필요 시 `롱 폴링` 또는 `SSE`

즉 결론은:

`이번 단계는 단순 폴링 기반 REST 채팅으로 구현하고, 롱 폴링은 2차 개선안으로 두는 것이 가장 현실적이다.`
