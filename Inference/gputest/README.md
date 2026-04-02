`gputest`는 현재 서비스 코드를 건드리지 않고, 원본급 처리 프로파일을 벤치하는 실험 폴더다.

현재 스크립트:
- `benchmark_native_e2e.py`
- `benchmark_forced_gpu_native_e2e.py`
- `benchmark_experimental_gpu_e2e.py`
- `benchmark_experimental_overlay_only_e2e.py`
- `benchmark_gpu_native_runtime.py`

현재 GPU 전용 재설계 모듈:
- `gpu_tensor_ops.py`
- `gpu_asset_cache.py`
- `gpu_legacy_overlay.py`
- `gpu_attenuation.py`
- `gpu_postprocess.py`
- `gpu_native_runtime.py`

문서:
- `gpu-native-design.md`
- `gpu-reimplementation-insights.md`

예시:
```bash
set -a
source .env.server
set +a
.venv/bin/python gputest/benchmark_native_e2e.py \
  --image testimage/긴머리_test.png \
  --stage 576x1024 \
  --dataset-code 0001 \
  --hair-id 1 \
  --iterations 8 \
  --process-dim 400 \
  --process-dim 560 \
  --process-dim 1024
```

의미:
- `process-dim 400`: 현재 운영과 비슷한 축소 처리
- `process-dim 560`: 중간 품질
- `process-dim 1024`: 576x1024 입력이면 사실상 원본급 처리

출력은 `prepare`, `runtime`, `attenuation`, `overlay`, `e2e_total`의 `avg/p50/p95`를 JSON으로 보여준다.

GPU 강제 실험:
```bash
set -a
source .env.server
set +a
.venv/bin/python gputest/benchmark_forced_gpu_native_e2e.py \
  --image testimage/긴머리_test.png \
  --stage 576x1024 \
  --dataset-code 0009 \
  --hair-id 3 \
  --iterations 3 \
  --process-dim 1024
```

의미:
- 원본 파일을 수정하지 않고, 런타임에서 `opencv_*` 호출을 GPU/torch CUDA 우선 래퍼로 갈아끼운 뒤 E2E를 벤치한다.

실험용 GPU 우선 파이프라인:
```bash
set -a
source .env.server
set +a
.venv/bin/python gputest/benchmark_experimental_gpu_e2e.py \
  --image testimage/긴머리_test.png \
  --stage 576x1024 \
  --dataset-code 0009 \
  --hair-id 3 \
  --iterations 3 \
  --process-dim 1024
```

의미:
- `gputest` 안에서만 attenuation과 legacy overlay를 더 단순한 GPU 우선 경로로 갈아끼운다.
- 서비스 원본 파일은 수정하지 않는다.

오버레이만 실험 GPU 경로:
```bash
set -a
source .env.server
set +a
.venv/bin/python gputest/benchmark_experimental_overlay_only_e2e.py \
  --image testimage/긴머리_test.png \
  --stage 576x1024 \
  --dataset-code 0009 \
  --hair-id 3 \
  --iterations 3 \
  --process-dim 1024
```

GPU 네이티브 재설계 벤치:
```bash
set -a
source .env.server
set +a
.venv/bin/python gputest/benchmark_gpu_native_runtime.py \
  --image testimage/긴머리_test.png \
  --stage 576x1024 \
  --dataset-code 0009 \
  --hair-id 3 \
  --iterations 6 \
  --warmup 1 \
  --process-dim 1024
```

의미:
- 기존 서비스 코드는 그대로 둔다.
- 선택/세션 로직은 원본 `HairOverlayRuntime`을 재사용한다.
- `attenuation`, `legacy overlay`, `postprocess`만 `gputest` GPU 모듈로 다시 구현한다.
- 목적은 `opencv 함수 단위 치환`이 아니라 `GPU 상주 stage`를 시험하는 것이다.

최근 steady-state 결과:
- 원본 baseline `576x1024`, `0009`, `6회`:
  - `e2e_total p50 428.0ms`
  - `attenuation p50 232.6ms`
  - `overlay p50 155.4ms`
- GPU native rebuild `576x1024`, `0009`, `6회 + warmup 1`:
  - `e2e_total p50 122.7ms`
  - `attenuation p50 42.5ms`
  - `overlay p50 45.2ms`
- 원본 baseline `576x1024`, `0010`, `6회`:
  - `e2e_total p50 426.8ms`
  - `attenuation p50 232.1ms`
  - `overlay p50 159.1ms`
- GPU native rebuild `576x1024`, `0010`, `6회 + warmup 1`:
  - `e2e_total p50 137.8ms`
  - `attenuation p50 46.4ms`
  - `overlay p50 52.8ms`

현재 해석:
- `opencv_*`를 무조건 GPU로 강제하는 방식은 실패했다.
- 대신 `torch.cuda` 기반으로 `legacy overlay`와 `attenuation`을 다시 짠 경로는 의미 있는 개선을 보였다.
- 아직 완전한 제품 수준은 아니다.
  - `lower_hairline_blend`, `eye_restore`, 일부 색 추정은 단순화돼 있다.
  - 첫 프레임 warmup 비용은 아직 크다.
