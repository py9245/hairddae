import type { NormalizedLandmark } from '@mediapipe/tasks-vision'

type PixelAnchor = {
  x: number
  y: number
  confidence: number
}

export type FaceAnchorSet = {
  forehead_center: PixelAnchor
  left_temple: PixelAnchor
  right_temple: PixelAnchor
  crown: PixelAnchor
  left_ear_root: PixelAnchor
  right_ear_root: PixelAnchor
  left_side: PixelAnchor
  right_side: PixelAnchor
  lower_left: PixelAnchor
  lower_right: PixelAnchor
  neck_left: PixelAnchor
  neck_right: PixelAnchor
}

const FACE_LANDMARK_INDEX = {
  forehead_top: 10,
  forehead_mid: 151,
  left_temple: 127,
  right_temple: 356,
  left_ear_root: 234,
  right_ear_root: 454,
  left_side: 93,
  right_side: 323,
  lower_left: 172,
  lower_right: 397,
  chin_center: 152,
} as const

function clamp(value: number, low: number, high: number) {
  return Math.max(low, Math.min(high, value))
}

function clampInt(value: number, low: number, high: number) {
  return Math.round(clamp(value, low, high))
}

function pointToPixel(
  landmarks: NormalizedLandmark[],
  index: number,
  width: number,
  height: number,
) {
  const point = landmarks[index]
  if (!point) {
    throw new Error(`missing landmark index: ${index}`)
  }

  return {
    x: point.x * width,
    y: point.y * height,
  }
}

function averagedPoint(points: Array<{ x: number; y: number }>) {
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  }
}

function toAnchor(point: { x: number; y: number }): PixelAnchor {
  return {
    x: Number(point.x.toFixed(3)),
    y: Number(point.y.toFixed(3)),
    confidence: 1,
  }
}

export function buildFaceAnchorPoints(
  landmarks: NormalizedLandmark[],
  width: number,
  height: number,
): FaceAnchorSet {
  const foreheadCenter = averagedPoint([
    pointToPixel(landmarks, FACE_LANDMARK_INDEX.forehead_top, width, height),
    pointToPixel(landmarks, FACE_LANDMARK_INDEX.forehead_mid, width, height),
  ])
  const chinCenter = pointToPixel(
    landmarks,
    FACE_LANDMARK_INDEX.chin_center,
    width,
    height,
  )
  const faceHeight = Math.max(1, chinCenter.y - foreheadCenter.y)
  const lowerLeft = pointToPixel(
    landmarks,
    FACE_LANDMARK_INDEX.lower_left,
    width,
    height,
  )
  const lowerRight = pointToPixel(
    landmarks,
    FACE_LANDMARK_INDEX.lower_right,
    width,
    height,
  )

  return {
    forehead_center: toAnchor(foreheadCenter),
    left_temple: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.left_temple, width, height),
    ),
    right_temple: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.right_temple, width, height),
    ),
    crown: toAnchor({
      x: clamp(foreheadCenter.x, 0, width - 1),
      y: clamp(foreheadCenter.y - faceHeight * 0.38, 0, height - 1),
    }),
    left_ear_root: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.left_ear_root, width, height),
    ),
    right_ear_root: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.right_ear_root, width, height),
    ),
    left_side: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.left_side, width, height),
    ),
    right_side: toAnchor(
      pointToPixel(landmarks, FACE_LANDMARK_INDEX.right_side, width, height),
    ),
    lower_left: toAnchor(lowerLeft),
    lower_right: toAnchor(lowerRight),
    neck_left: toAnchor({
      x: clamp(lowerLeft.x, 0, width - 1),
      y: clamp(lowerLeft.y + faceHeight * 0.22, 0, height - 1),
    }),
    neck_right: toAnchor({
      x: clamp(lowerRight.x, 0, width - 1),
      y: clamp(lowerRight.y + faceHeight * 0.22, 0, height - 1),
    }),
  }
}

export function buildFaceBoundingBox(
  landmarks: NormalizedLandmark[],
  width: number,
  height: number,
) {
  if (!landmarks.length) {
    return {
      x: 0,
      y: 0,
      w: width,
      h: height,
    }
  }

  let minX = Number.POSITIVE_INFINITY
  let minY = Number.POSITIVE_INFINITY
  let maxX = Number.NEGATIVE_INFINITY
  let maxY = Number.NEGATIVE_INFINITY

  for (const landmark of landmarks) {
    const x = landmark.x * width
    const y = landmark.y * height
    minX = Math.min(minX, x)
    minY = Math.min(minY, y)
    maxX = Math.max(maxX, x)
    maxY = Math.max(maxY, y)
  }

  const clampedMinX = clampInt(minX, 0, width - 1)
  const clampedMinY = clampInt(minY, 0, height - 1)
  const clampedMaxX = clampInt(maxX, 0, width - 1)
  const clampedMaxY = clampInt(maxY, 0, height - 1)

  return {
    x: clampedMinX,
    y: clampedMinY,
    w: Math.max(0, clampedMaxX - clampedMinX),
    h: Math.max(0, clampedMaxY - clampedMinY),
  }
}
