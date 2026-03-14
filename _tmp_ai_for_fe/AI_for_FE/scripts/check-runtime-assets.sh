#!/usr/bin/env bash
set -eu

PUBLIC_ROOT="${1:-./public}"

fail() {
  echo "missing: $1" >&2
  exit 1
}

test -d "$PUBLIC_ROOT" || fail "$PUBLIC_ROOT"
test -f "$PUBLIC_ROOT/models/face_landmarker.task" || fail "$PUBLIC_ROOT/models/face_landmarker.task"
test -d "$PUBLIC_ROOT/mediapipe" || fail "$PUBLIC_ROOT/mediapipe"

echo "runtime assets ok: $PUBLIC_ROOT"
