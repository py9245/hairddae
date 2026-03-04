## 전체적인 진행 로직
- 가이드 라인 내에 얼굴을 제대로 위치하고 3초 지나면 데이터 전송 시작
- 매 프레임당 랜드마크를 저장하고 1000ms마다 축적된 랜드마크 data를 보냄
- 정면을 시작으로 좌, 우 한번씩 인식시키면 전송 끝남
- 백엔드 api 연결 로직 대신 현재는 모든 전송이 끝난후 해당 data json파일로 저장시킴
- 원래는 +-75도로 정했지만 그것도 꽤 많이 고개를 많이 돌려야해서 현재는 30도로 조정해놈
- 정면, 좌, 우 모두 인식 끝나면 json 파일 다운로드됨


## 현재 json data
- 1000ms당 전송 진행
- 아래의 형식처럼 data 저장
```json
"1000": {
  "bucketMs": "전송 시작 기준 이 버킷의 경과 시간(ms)이며 1000ms 단위",
  "frameCount": "해당 1초 구간(버킷) 안에 기록된 프레임",
  "progress": {
    "leftSeen": "전송 시작 후 왼쪽 감지 여부",
    "rightSeen": "전송 시작 후 오른쪽 감지 여부"
  },
  "frames": [
    {
      "t": "performance.now()기반의 페이지 기준 상대 시간",
      "status": "포즈 분류 결과 front/left/right/none",
      "inGuide": "얼굴이 가이드 안에 들어와있는지",
      "faceFound": "해당 시점에 얼굴 랜드마크가 감지 되었는지",
      "pose": {
        "pitch": "고개 상하 회전 각도",
        "yaw": "고개 좌우 회전 각도",
        "roll": "고개 기울기 회전 각도"
      },
      "landmarks": "얼굴 랜드마크 전체 점들의 정규화 좌표 배열"
    }
  ]
}

```

## 파일별 역할
- components/FaceLandmarks.tsx: 카메라/모델 훅을 초기화하고 트래킹 루프와 전송 플로우 훅을 조립해 View에 props로 내려주는 컨테이너다.
- components/FaceLandmarksView.tsx: video/canvas/가이드 오버레이와 상태 텍스트를 렌더링하는 UI 전용 컴포넌트다.
- components/AlignmentGuide.tsx: 정면/좌/우 상태에 따라 가이드 라인 및 안내 오버레이를 그리는 컴포넌트다.
- hooks/useUserMedia.ts: getUserMedia로 카메라 스트림을 연결하고 video 엘리먼트에 바인딩하는 훅이다.
- hooks/useFaceLandmarker.ts: MediaPipe FaceLandmarker 모델/wasm을 로드하고 landmarker 인스턴스를 제공하는 훅이다.
- hooks/useFaceTrackingLoop.ts: requestAnimationFrame 루프로 매 프레임 추론을 수행하고 inGuide/status를 계산하며 캔버스에 랜드마크를 그리는 훅이다.
- hooks/useMockTransmitFlow.ts: 정면 3초 유지 시 전송을 시작하고 100ms마다 payload를 누적·mock 전송하며 좌/우 1회 인식 시 종료하는 훅이다.
- lib/face/types.ts: PoseStatus, PoseAngles, FaceFrame 등 얼굴 트래킹/전송에 쓰는 공용 타입을 정의한다.
- lib/face/guide.ts: 랜드마크가 가이드 타원 영역 안에 들어오는지 판정하는 로직과 관련 상수를 담는다.
- lib/face/pose.ts: 변환 행렬로부터 yaw/pitch/roll을 계산하고 포즈를 front/left/right/none으로 분류하는 유틸이다.
- lib/face/draw.ts: 랜드마크 점들을 캔버스에 렌더링하는 디버그 드로잉 유틸이다.
- lib/face/downloadJson.ts: 누적된 로그 객체를 JSON 파일로 만들어 브라우저 다운로드로 내보내는 유틸이다.


## 현재 문제점과 실제 구현시 예상 문제점
- 당연할수도 있지만 성능최적화는 아무것도 안돼있어서 크롬 DevTools에서 프레임당 콜백시간이 너무 오래걸렸다고 경고 발생
  - 기준 16ms인데 현재 50~65ms 나옴
  - MediaPipe 추론 자체가 많이 무거움
  - 해상도도 높은편
  - 캔버스에 400개가 넘는 점을 그리는중
  - 불필요한 객체를 많이 생성중

- 실제 구현시 ux 개선점
  - 고개를 너무 빠르게 돌리거나 너무 느리게 돌리면 처음부터 다시하기 안내같은게 필요
  - 중간에 가이드라인 벗어났을때도 대책 필요
  - 고개 돌릴때 화살표 방향 애니메이션 추가필요



## 대머리 처리
- ROI 
  - 우리가 집중해서 처리할 화면의 영역(범위)
  - 이 프로젝트에선 두피가 있어야 하는 영역

- 대머리 필터는 결국
  - 머리카락을 지울 영역과
  - 두피를 채울 영역

  2) AI 학습이 “필요해지는” 경우

3D 메시를 “더 진짜처럼” 만들려면 다음 단계에서 학습이 등장할 수 있어.

A. 개인별 두개골 형태까지 추정하고 싶다

사진 한 장(또는 짧은 영상)으로 정수리 높이, 후두부 돌출, 머리 폭 같은 걸 추정

이건 사실상 “head shape estimation”이라 모델이 필요할 수 있음

B. 머리카락 제거 후 “진짜 두피 텍스처”를 생성하고 싶다

인페인팅/생성 모델로 머리카락 영역을 자연스럽게 복원

실시간 모바일에선 무겁고, 서버 추론이면 가능

C. 세그멘테이션 자체 품질을 극도로 올리고 싶다

hair segmentation이 제일 병목인데,

특정 환경(미용실 조명/배경/카메라) 맞춤으로 성능을 끌어올리려면 파인튜닝이 유리할 수 있음

