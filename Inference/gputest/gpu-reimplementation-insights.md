`gputest` GPU 재구현 인사이트

목적
- 현재 배포 기능은 유지한다.
- 원본 서비스 코드는 손대지 않는다.
- `gputest` 안에서만 GPU 전용 파이프라인을 다시 설계한다.
- 단순히 `opencv_*`를 GPU로 강제하는 것이 아니라, 단계 자체를 GPU 친화적으로 다시 짠다.

현재 결론 요약
- 원본급 `576x1024` 기준 baseline은 `e2e p50 399.5ms`
- `opencv_*`를 전부 GPU로 강제한 버전은 `e2e p50 1010.3ms`
- 실험용 GPU attenuation + GPU overlay는 `e2e p50 471.4ms`
- 실험용 GPU overlay만 바꾼 버전은 `e2e p50 404.5ms`

즉 지금 얻은 교훈은 하나다.
- `함수 단위 GPU 강제`는 실패한다
- `stage 단위 GPU 상주 구조`로 다시 설계해야 한다

현재 환경에서 바로 쓸 수 있는 GPU 도구
- `torch 2.10.0+cu128`
- `torchvision 0.25.0+cu128`
- `torch.cuda` 사용 가능
- `torch.nn.functional.grid_sample` 사용 가능
- `torch.nn.functional.interpolate` 사용 가능
- `torch.nn.functional.conv2d` 사용 가능
- `torch.nn.functional.max_pool2d` 사용 가능
- `cv2.cuda` 사용 가능

현재 환경에서 바로 못 쓰는 것
- `cv2.cuda.createGaussianFilter`
- `cv2.cuda.createMorphologyFilter`
- 즉 OpenCV Python CUDA로 blur/morphology를 직접 처리하는 길은 사실상 없다

현재 CPU 구현과 GPU 대체 후보

1. `prepare_runtime_frame`
- 현재 역할
  - `BGR -> RGB`
  - face tracking, hair segmentation 병렬 실행
  - attenuation 호출
- 현재 CPU/혼합 이유
  - 프레임이 `numpy`로 들어오고, 이후 단계도 `numpy` 중심
- GPU 대체안
  - 현재 그대로 유지해도 됨
  - 핵심은 이후 `attenuation`과 `overlay`를 GPU 텐서로 이어받는 것
- 추천 라이브러리
  - `torch.cuda`
  - `cv2.cuda.cvtColor` 또는 `torch` 텐서 변환

2. `HairAttenuator.apply_with_metadata`
- 현재 역할
  - hair segmentation confidence를 알파로 만듦
  - `fringe`, `hair_binary`, `outer_bulk`, `background_color`, `scalp_color` 계산
  - blur, morphology, 색 추정, lower hairline blend, eye restore 수행
- 현재 CPU 기준으로 선택된 구현
  - `cv2.GaussianBlur`, `dilate`, `erode`, `connectedComponents`, Python 열 단위 루프
- GPU 대체안
  - `GaussianBlur` -> `torch.conv2d`
  - `dilate/erode` -> `max_pool2d` / `-max_pool2d(-x)` 패턴
  - `resize` -> `torch.nn.functional.interpolate`
  - `bitwise/mask 연산` -> `torch` boolean/float 텐서 연산
  - `ROI blend` -> `torch` alpha blend
  - `lower_hairline_blend` -> Python 열 루프 대신 `torch` column field interpolate
- 바로 GPU로 옮기기 쉬운 부분
  - alpha blur
  - ROI blend
  - 마스크 dilation/erosion
- CPU로 남겨도 되는 작은 부분
  - landmark 기반 점 계산
  - 색 추정용 작은 patch 좌표 계산
- 새 라이브러리 후보
  - 즉시 가능: `torch.cuda`
  - 추가 설치 후보: `kornia` (`warp_affine`, morphology, color ops)

3. `build_effective_alpha`
- 현재 역할
  - warped alpha와 warped hair를 결합해서 최종 합성 alpha 생성
  - hair blur, soft blur, alpha gain 적용
- 현재 CPU 기준 구현
  - OpenCV blur 두 번
- GPU 대체안
  - `torch.minimum`
  - `torch.conv2d` Gaussian kernel
  - `alpha_gain`도 텐서 곱으로 처리
- 추천
  - 이 부분은 GPU화 이득이 크다
  - `legacy overlay`에 포함시켜 한 번에 처리하는 것이 좋다

4. `apply_asset_skin_suppression_gain`
- 현재 역할
  - protect/face/ear 쪽에서 alpha를 낮춰 얼굴 침범을 억제
- 현재 CPU 기준 구현
  - 마스크 여러 장 blur
  - 게이트 계산
  - alpha에 다시 곱
- GPU 대체안
  - protect/face/ear 마스크를 stacked tensor로 보관
  - 각 마스크 blur는 `torch.conv2d`
  - 게이트 계산은 elementwise 텐서 연산
- 주의
  - 이 단계는 “기능 유지”에는 중요하지만, 마스크 수를 줄이는 설계가 더 중요하다
  - `legacy`는 우선 `protect_face` 중심으로 단순화하는 것이 현실적이다

5. `build_legacy_overlay_layer`
- 현재 역할
  - asset 선택 후 실제 RGB/alpha/hair/protect를 사용자 얼굴 위치에 맞게 warp
  - tone gain, effective alpha, skin suppression, coverage 생성
- 현재 CPU 기준으로 좋았던 이유
  - mesh보다 구조가 단순
  - 기준점 4개 중심 affine이라 이해하기 쉽다
- 현재 GPU 재구현 방향
  - asset를 `torch.cuda` 텐서 캐시에 보관
  - affine matrix는 CPU 계산
  - 실제 warp는 `torch.nn.functional.affine_grid` + `grid_sample`
  - `rgb`, `alpha`, `hair`, `protect`를 stacked tensor로 한 번에 warp
  - coverage mask는 `warped_alpha/hair`에서 즉시 생성
- 추천 라이브러리
  - 즉시 가능: `torch.cuda`
  - 추가 설치 후보: `kornia.geometry.transform.warp_affine`

6. `compose_overlay_frame` / `composite_effective_layer`
- 현재 역할
  - warped RGB + alpha를 base frame 위에 합성
- 현재 CPU 기준 구현
  - `numpy float32` blend 후 `uint8` 복원
- GPU 대체안
  - `result = base * (1 - alpha) + rgb * alpha`
  - 전부 `torch.cuda`에서 수행
- 추천
  - 이 부분은 반드시 GPU 상주로 가져가야 함
  - 그래야 warp 후 CPU로 바로 내리는 낭비를 막을 수 있음

7. `apply_overlay_postprocess`
- 현재 역할
  - `hair_binary - coverage`에서 residual hair만 배경화
  - `fringe`, `face_protect`는 제외
- 현재 CPU 기준 구현
  - residual mask 계산
  - bounding box ROI
  - 작은 blur와 background blend
- GPU 대체안
  - residual mask 계산은 텐서 차집합으로 바로 가능
  - 배경색 field도 열 방향 텐서 interpolate 가능
  - ROI 최적화는 나중, 우선 전체 텐서 마스크로 단순 구현 후 최적화

권장 GPU 전용 모듈 구조
- `gpu_tensor_ops.py`
  - 텐서 변환, blur, morphology, alpha blend, mask utilities
- `gpu_attenuation.py`
  - segmentation confidence -> alpha
  - fringe/binary/protect 마스크 결합
  - scalp/background color 적용
  - lower hairline blend
- `gpu_asset_cache.py`
  - asset RGB/alpha/hair/protect를 GPU 텐서 캐시로 유지
- `gpu_legacy_overlay.py`
  - affine grid 생성
  - stacked warp
  - effective alpha
  - protect suppression
  - coverage 생성
- `gpu_postprocess.py`
  - `hair_binary - coverage - fringe - face_protect`
  - residual background cleanup
- `gpu_e2e_runner.py`
  - current benchmark처럼 전체 파이프라인을 연결

라이브러리별 인사이트

`OpenCV CUDA`
- 장점
  - resize, cvtColor, warpAffine는 빠르게 붙일 수 있음
- 한계
  - Python 바인딩에 blur/morphology filter가 없음
  - 작은 연산이 많아지면 업로드/다운로드 비용이 커짐
- 결론
  - 보조 도구로는 좋지만, 전체 파이프라인 주축으로는 부족함

`torch.cuda`
- 장점
  - `grid_sample`, `interpolate`, `conv2d`, `max_pool2d`로 대부분의 영상 처리 기본기를 대체 가능
  - 텐서를 GPU에 오래 유지하기 좋음
- 한계
  - 단순 OpenCV 치환보다 구현량이 큼
  - 색 추정, 연결요소 같은 일부 로직은 따로 단순화가 필요
- 결론
  - 현재 환경에서 가장 현실적인 GPU 네이티브 주력 후보

`kornia`
- 장점
  - `warp_affine`, morphology, color transform 같은 비전 연산이 더 자연스럽다
- 한계
  - 현재 환경에 설치돼 있지 않음
- 결론
  - 추가 설치 가능하면 가장 좋은 보조 라이브러리 후보

`cupy`
- 장점
  - numpy 스타일 커널 작성이 쉬움
- 한계
  - 현재 환경에 없음
  - 파이프라인 전체 주력으로 쓰기엔 torch와 중복
- 결론
  - 우선순위 낮음

`NVIDIA DALI`
- 장점
  - 디코드/리사이즈/전처리 쪽엔 매우 강함
- 한계
  - 현재 hair attenuation/legacy overlay 같은 커스텀 합성 로직엔 바로 맞지 않음
- 결론
  - 장기적으로 디코드/입력 파이프라인에만 검토

실행 우선순위
1. `gpu_tensor_ops.py`
  - blur / morphology / alpha blend / stacked warp 유틸 만들기
2. `gpu_legacy_overlay.py`
  - 현재 `legacy` 기능을 동일하게 재구현
3. `gpu_attenuation.py`
  - 현재 기능 중 꼭 필요한 것만 유지한 fast path부터 구현
4. `gpu_postprocess.py`
  - coverage 기반 residual cleanup 연결
5. `gpu_e2e_runner.py`
  - benchmark와 실제 품질 비교

바로 버려야 할 안티패턴
- `opencv_*` 호출마다 GPU 업로드/다운로드
- 작은 blur/morphology를 전부 개별 GPU 작업으로 쪼개기
- `numpy -> torch -> numpy` 왕복 반복
- coverage를 `absdiff`로 추정하는 것

핵심 결론
- 현재 구조에서 “GPU로 그냥 바꾸기”는 의미가 작다
- `torch.cuda`를 주력으로 한 GPU 상주 파이프라인으로 다시 짜야 한다
- 첫 타겟은 `legacy overlay`, 둘째는 `attenuation`
