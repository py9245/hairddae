import type { NormalizedLandmark } from '@mediapipe/tasks-vision'
import type { AssetAnchors, AssetMetadata } from '@/runtime/asset-runtime'

export type Point2 = {
  x: number
  y: number
}

export type Affine2D = {
  m00: number
  m01: number
  m02: number
  m10: number
  m11: number
  m12: number
}

export type BoundingBox = {
  x: number
  y: number
  w: number
  h: number
}

const LIVE_ANCHOR_INDICES = {
  forehead_center: [10],
  left_temple: [127, 234],
  right_temple: [356, 454],
  left_side: [234],
  right_side: [454],
  lower_left: [172],
  lower_right: [397],
} as const

function getCoverRect(
  videoWidth: number,
  videoHeight: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  const scale = Math.max(canvasWidth / videoWidth, canvasHeight / videoHeight)
  const drawWidth = videoWidth * scale
  const drawHeight = videoHeight * scale

  return {
    scale,
    offsetX: (canvasWidth - drawWidth) / 2,
    offsetY: (canvasHeight - drawHeight) / 2,
  }
}

function landmarkToCanvasPoint(
  landmark: NormalizedLandmark,
  videoWidth: number,
  videoHeight: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  const { offsetX, offsetY, scale } = getCoverRect(
    videoWidth,
    videoHeight,
    canvasWidth,
    canvasHeight,
  )

  return {
    x: offsetX + landmark.x * videoWidth * scale,
    y: offsetY + landmark.y * videoHeight * scale,
  }
}

function averageLandmarks(
  landmarks: NormalizedLandmark[],
  indices: readonly number[],
  videoWidth: number,
  videoHeight: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  const points = indices
    .map((index) => landmarks[index])
    .filter((value): value is NormalizedLandmark => !!value)
    .map((landmark) =>
      landmarkToCanvasPoint(
        landmark,
        videoWidth,
        videoHeight,
        canvasWidth,
        canvasHeight,
      ),
    )

  if (points.length === 0) {
    return null
  }

  const total = points.reduce(
    (acc, point) => ({
      x: acc.x + point.x,
      y: acc.y + point.y,
    }),
    { x: 0, y: 0 },
  )

  return {
    x: total.x / points.length,
    y: total.y / points.length,
  }
}

function buildLiveAnchorMap(
  landmarks: NormalizedLandmark[],
  videoWidth: number,
  videoHeight: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  return {
    forehead_center: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.forehead_center,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    left_temple: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.left_temple,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    right_temple: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.right_temple,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    left_side: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.left_side,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    right_side: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.right_side,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    lower_left: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.lower_left,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
    lower_right: averageLandmarks(
      landmarks,
      LIVE_ANCHOR_INDICES.lower_right,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
  }
}

function invert3x3(matrix: number[][]) {
  const [
    [a, b, c],
    [d, e, f],
    [g, h, i],
  ] = matrix

  const A = e * i - f * h
  const B = -(d * i - f * g)
  const C = d * h - e * g
  const D = -(b * i - c * h)
  const E = a * i - c * g
  const F = -(a * h - b * g)
  const G = b * f - c * e
  const H = -(a * f - c * d)
  const I = a * e - b * d

  const determinant = a * A + b * B + c * C
  if (Math.abs(determinant) < 1e-8) {
    return null
  }

  const scale = 1 / determinant

  return [
    [A * scale, D * scale, G * scale],
    [B * scale, E * scale, H * scale],
    [C * scale, F * scale, I * scale],
  ]
}

function multiplyMatrixVector(matrix: number[][], vector: number[]) {
  return matrix.map(
    (row) =>
      row[0] * vector[0] + row[1] * vector[1] + row[2] * vector[2],
  )
}

function solveAffine(
  src: [Point2, Point2, Point2],
  dst: [Point2, Point2, Point2],
) {
  const matrix = [
    [src[0].x, src[0].y, 1],
    [src[1].x, src[1].y, 1],
    [src[2].x, src[2].y, 1],
  ]

  const inverse = invert3x3(matrix)
  if (!inverse) {
    return null
  }

  const [m00, m01, m02] = multiplyMatrixVector(inverse, [
    dst[0].x,
    dst[1].x,
    dst[2].x,
  ])
  const [m10, m11, m12] = multiplyMatrixVector(inverse, [
    dst[0].y,
    dst[1].y,
    dst[2].y,
  ])

  return {
    m00,
    m01,
    m02,
    m10,
    m11,
    m12,
  }
}

function buildFaceBboxAffine(
  metadata: AssetMetadata,
  landmarks: NormalizedLandmark[],
  videoWidth: number,
  videoHeight: number,
  canvasWidth: number,
  canvasHeight: number,
) {
  if (landmarks.length === 0) {
    return null
  }

  const points = landmarks.map((landmark) =>
    landmarkToCanvasPoint(
      landmark,
      videoWidth,
      videoHeight,
      canvasWidth,
      canvasHeight,
    ),
  )

  const minX = Math.min(...points.map((point) => point.x))
  const maxX = Math.max(...points.map((point) => point.x))
  const minY = Math.min(...points.map((point) => point.y))
  const maxY = Math.max(...points.map((point) => point.y))

  const liveWidth = Math.max(1, maxX - minX)
  const liveHeight = Math.max(1, maxY - minY)
  const source = metadata.face_bbox

  const scaleX = liveWidth / source.w
  const scaleY = liveHeight / source.h

  return {
    m00: scaleX,
    m01: 0,
    m02: minX - source.x * scaleX,
    m10: 0,
    m11: scaleY,
    m12: minY - source.y * scaleY,
  }
}

export function buildOverlayAffine({
  metadata,
  anchors,
  landmarks,
  videoWidth,
  videoHeight,
  canvasWidth,
  canvasHeight,
}: {
  metadata: AssetMetadata
  anchors: AssetAnchors
  landmarks: NormalizedLandmark[]
  videoWidth: number
  videoHeight: number
  canvasWidth: number
  canvasHeight: number
}) {
  const liveAnchors = buildLiveAnchorMap(
    landmarks,
    videoWidth,
    videoHeight,
    canvasWidth,
    canvasHeight,
  )

  const sourceForehead = anchors.anchors.forehead_center
  const sourceLeftTemple = anchors.anchors.left_temple
  const sourceRightTemple = anchors.anchors.right_temple

  if (
    sourceForehead &&
    sourceLeftTemple &&
    sourceRightTemple &&
    liveAnchors.forehead_center &&
    liveAnchors.left_temple &&
    liveAnchors.right_temple
  ) {
    const affine = solveAffine(
      [
        { x: sourceForehead.x, y: sourceForehead.y },
        { x: sourceLeftTemple.x, y: sourceLeftTemple.y },
        { x: sourceRightTemple.x, y: sourceRightTemple.y },
      ],
      [
        liveAnchors.forehead_center,
        liveAnchors.left_temple,
        liveAnchors.right_temple,
      ],
    )

    if (affine) {
      return affine
    }
  }

  return buildFaceBboxAffine(
    metadata,
    landmarks,
    videoWidth,
    videoHeight,
    canvasWidth,
    canvasHeight,
  )
}

export type DrawHairOverlayArgs = {
  ctx: CanvasRenderingContext2D
  image: CanvasImageSource
  bbox: BoundingBox
  affine: Affine2D
  alpha?: number
}

export function drawHairOverlayToCanvas({
  ctx,
  image,
  bbox,
  affine,
  alpha = 1,
}: DrawHairOverlayArgs) {
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.setTransform(
    affine.m00,
    affine.m10,
    affine.m01,
    affine.m11,
    affine.m02,
    affine.m12,
  )
  ctx.drawImage(image, bbox.x, bbox.y, bbox.w, bbox.h)
  ctx.restore()
}

export function interpolateAffine(
  from: Affine2D,
  to: Affine2D,
  t: number,
): Affine2D {
  const lerp = (a: number, b: number) => a + (b - a) * t
  return {
    m00: lerp(from.m00, to.m00),
    m01: lerp(from.m01, to.m01),
    m02: lerp(from.m02, to.m02),
    m10: lerp(from.m10, to.m10),
    m11: lerp(from.m11, to.m11),
    m12: lerp(from.m12, to.m12),
  }
}
