`gputest` GPU 전용 파이프라인 설계 초안

목표
- 현재 배포 기능과 같은 사용자 경험을 유지한다.
- `face landmark`와 `hair segmentation` 이후 단계는 가능한 한 한 번만 GPU에 올리고 끝까지 GPU에서 처리한다.
- 현재 기준 해상도는 `576x1024`를 우선 타깃으로 하고, 이후 `432x768`도 같은 구조로 확장한다.

핵심 원칙
- `numpy/OpenCV/PIL`를 섞지 않는다.
- 프레임 업로드는 1회, 다운로드는 마지막 1회만 목표로 한다.
- `attenuation`, `legacy overlay`, `postprocess`를 각각 별도 함수가 아니라 하나의 GPU 그래프처럼 묶는다.
- 알파, 마스크, RGB는 모두 `torch.cuda` 텐서로 들고 간다.

권장 단계
1. 입력 프레임 업로드
- `BGR uint8 numpy`를 `torch.float32 CUDA`로 한 번만 올린다.
- `NCHW` 텐서와 `HWC` 뷰를 모두 지원하는 래퍼를 둔다.

2. GPU attenuation
- 세그멘테이션 confidence를 GPU 알파로 변환한다.
- landmark 기반 `fringe`, `binary`, `face_protect`는 CPU에서 마스크 좌표만 만들고 즉시 GPU 마스크 텐서로 넘긴다.
- 피부색 추정은 작은 패치 샘플링만 CPU 또는 `torch` reduce로 처리한다.
- 큰 blur, morphology, alpha blend는 `torch.cuda`로 수행한다.
- `lower_hairline_blend`는 열 단위 Python 루프 대신 GPU field interpolate 형태로 바꾼다.

3. GPU asset cache
- 자주 쓰는 asset의 `rgb`, `alpha`, `hair`, `protect_face`를 GPU 텐서 캐시로 유지한다.
- 현재 `legacy` 기준으로 필요한 마스크만 올린다.
- `face`, `ear`는 품질 이득이 확실할 때만 선택적으로 붙인다.

4. GPU legacy overlay
- anchor 기반 affine matrix는 CPU에서 계산해도 된다.
- 실제 warp는 `grid_sample` 또는 `cv2.cuda.warpAffine`로 수행한다.
- `rgb`, `alpha`, `hair`, `protect_face`는 한 번에 처리 가능한 stacked tensor 구조를 우선 검토한다.
- `effective alpha`, `skin suppression`, `coverage mask`는 같은 GPU 텐서 흐름 안에서 만든다.

5. GPU postprocess
- 후보 마스크는 `hair_binary - asset_coverage`를 기본으로 한다.
- `fringe`, `face_protect`를 뺀 뒤 residual만 배경화한다.
- 이 단계도 ROI가 아니라 전체 텐서 마스크 연산으로 먼저 맞추고, 필요 시 ROI 최적화를 추가한다.

6. 출력
- 최종 `torch.cuda` 텐서를 한 번만 CPU `uint8`로 내린다.
- 장기적으로는 `NVENC` 직결 구조를 목표로 한다.

현재 실험 결론
- `모든 opencv_* 호출을 GPU로 강제`하는 방식은 느렸다.
- 원인은 작은 연산마다 CPU↔GPU 왕복이 생기기 때문이다.
- 의미 있는 방향은 `개별 함수 GPU화`가 아니라 `stage 단위 GPU 상주`다.

우선순위
1. `attenuation` 재설계
2. `legacy overlay` 재설계
3. `coverage mask`와 `postprocess` 결합
4. asset GPU 캐시
5. 최종 디코드/인코드 GPU 직결
