# Missing RGB Repair

`0004`, `0010`처럼 `metadata.image_path`는 잡혀 있지만 실제 `rgb/*.png` 파일이 비어 있는 데이터셋이 있습니다.

이 상태에서는 overlay 경로가 `hair_rgba` crop을 대신 읽다가, full-frame 마스크와 크기가 달라져 OpenCV shape assert가 날 수 있습니다.

원클릭 복구:

```bash
./scripts/synthesize_missing_rgb_all.sh
```

동작:

- `static/*/manifests/asset_index_v0.json` 이 있는 모든 데이터셋을 탐색
- 각 asset의 `image_path`가 이미 있으면 건너뜀
- 없으면 `hair_rgba_path + hair_rgba_bbox + image_size`로 full-frame `rgb/*.png` 생성

유용한 옵션:

```bash
./scripts/synthesize_missing_rgb_all.sh --dry-run
./scripts/synthesize_missing_rgb_all.sh --dataset-code 0010
./scripts/synthesize_missing_rgb_all.sh --dataset-code 0004 --limit-per-dataset 10 --dry-run
```

주의:

- 생성되는 `rgb/*.png`는 원본 RGB 복원본이 아니라, `hair_rgba`를 full-frame 캔버스에 배치한 계약 복구용 이미지입니다.
- 대량 생성 시 디스크 사용량이 꽤 늘어날 수 있습니다.
