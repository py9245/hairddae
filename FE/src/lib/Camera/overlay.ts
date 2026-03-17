import type { NormalizedLandmark } from '@mediapipe/tasks-vision'

import { buildFaceAnchorPoints, type FaceAnchorSet } from '@/lib/Camera/anchors'
import {
  fetchHairAssetIndex,
  type HairApplyV2Response,
  type HairAssetIndexBundle,
  type InferenceAssetBundle,
  type InferenceRenderTask,
} from '@/lib/Camera/inference'
import { getVideoCoverLayout } from '@/lib/Camera/layout'

type Point = {
  x: number
  y: number
}

type AssetAnchorsPayload = {
  anchors: FaceAnchorSet
}

export type OverlayAssetSource = Pick<
  InferenceAssetBundle,
  'assetId' | 'hairRgbaUrl' | 'anchorsUrl' | 'hairBBox'
>

export type OverlayAssetBundle = {
  assetId: string
  image: HTMLImageElement
  anchors: FaceAnchorSet
  hairBBox: { x: number; y: number; w: number; h: number } | null
}

type Matrix2D = {
  a: number
  b: number
  c: number
  d: number
  e: number
  f: number
}

const overlayBundleCache = new Map<string, OverlayAssetBundle>()
const overlayBundlePromiseCache = new Map<
  string,
  Promise<OverlayAssetBundle | null>
>()

function loadImage(src: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.crossOrigin = 'anonymous'
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`image load failed: ${src}`))
    image.src = src
  })
}

async function loadAssetAnchors(url: string) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`anchors load failed: ${response.status}`)
  }
  return (await response.json()) as AssetAnchorsPayload
}

function getTransformPoints(anchors: FaceAnchorSet): Point[] {
  return [
    anchors.left_temple,
    anchors.right_temple,
    anchors.forehead_center,
    anchors.crown,
  ]
}

function shiftPoint(point: Point, originX: number, originY: number): Point {
  return {
    x: point.x - originX,
    y: point.y - originY,
  }
}

function solveLinearSystem(matrix: number[][], vector: number[]) {
  const n = matrix.length
  const augmented = matrix.map((row, index) => [...row, vector[index]])

  for (let pivot = 0; pivot < n; pivot += 1) {
    let maxRow = pivot
    for (let row = pivot + 1; row < n; row += 1) {
      if (Math.abs(augmented[row][pivot]) > Math.abs(augmented[maxRow][pivot])) {
        maxRow = row
      }
    }

    const pivotValue = augmented[maxRow][pivot]
    if (!Number.isFinite(pivotValue) || Math.abs(pivotValue) < 1e-8) {
      return null
    }

    if (maxRow !== pivot) {
      ;[augmented[pivot], augmented[maxRow]] = [
        augmented[maxRow],
        augmented[pivot],
      ]
    }

    for (let row = pivot + 1; row < n; row += 1) {
      const factor = augmented[row][pivot] / augmented[pivot][pivot]
      for (let col = pivot; col <= n; col += 1) {
        augmented[row][col] -= factor * augmented[pivot][col]
      }
    }
  }

  const solution = new Array<number>(n)
  for (let row = n - 1; row >= 0; row -= 1) {
    let sum = augmented[row][n]
    for (let col = row + 1; col < n; col += 1) {
      sum -= augmented[row][col] * solution[col]
    }
    solution[row] = sum / augmented[row][row]
  }

  return solution
}

function estimateSimilarityTransform(
  sourcePoints: Point[],
  destinationPoints: Point[],
): Matrix2D | null {
  const ata = Array.from({ length: 4 }, () => new Array<number>(4).fill(0))
  const atb = new Array<number>(4).fill(0)

  for (let index = 0; index < sourcePoints.length; index += 1) {
    const source = sourcePoints[index]
    const destination = destinationPoints[index]
    const rows = [
      [source.x, -source.y, 1, 0],
      [source.y, source.x, 0, 1],
    ]
    const outputs = [destination.x, destination.y]

    for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex]
      const output = outputs[rowIndex]
      for (let i = 0; i < 4; i += 1) {
        atb[i] += row[i] * output
        for (let j = 0; j < 4; j += 1) {
          ata[i][j] += row[i] * row[j]
        }
      }
    }
  }

  const solution = solveLinearSystem(ata, atb)
  if (!solution) {
    return null
  }

  const [a, b, tx, ty] = solution
  return {
    a,
    b,
    c: -b,
    d: a,
    e: tx,
    f: ty,
  }
}

function estimateAffineFromThreePoints(
  sourcePoints: Point[],
  destinationPoints: Point[],
): Matrix2D | null {
  if (sourcePoints.length < 3 || destinationPoints.length < 3) {
    return null
  }

  const matrix = [
    [sourcePoints[0].x, sourcePoints[0].y, 1, 0, 0, 0],
    [0, 0, 0, sourcePoints[0].x, sourcePoints[0].y, 1],
    [sourcePoints[1].x, sourcePoints[1].y, 1, 0, 0, 0],
    [0, 0, 0, sourcePoints[1].x, sourcePoints[1].y, 1],
    [sourcePoints[2].x, sourcePoints[2].y, 1, 0, 0, 0],
    [0, 0, 0, sourcePoints[2].x, sourcePoints[2].y, 1],
  ]
  const vector = [
    destinationPoints[0].x,
    destinationPoints[0].y,
    destinationPoints[1].x,
    destinationPoints[1].y,
    destinationPoints[2].x,
    destinationPoints[2].y,
  ]

  const solution = solveLinearSystem(matrix, vector)
  if (!solution) {
    return null
  }

  const [a, c, e, b, d, f] = solution
  return { a, b, c, d, e, f }
}

function buildDestinationAnchors(
  landmarks: NormalizedLandmark[],
  canvasWidth: number,
  canvasHeight: number,
  videoWidth: number,
  videoHeight: number,
): FaceAnchorSet {
  const sourceAnchors = buildFaceAnchorPoints(landmarks, videoWidth, videoHeight)
  const { scale, offsetX, offsetY } = getVideoCoverLayout(
    canvasWidth,
    canvasHeight,
    videoWidth,
    videoHeight,
  )

  const mappedEntries = Object.entries(sourceAnchors).map(([key, value]) => [
    key,
    {
      x: value.x * scale + offsetX,
      y: value.y * scale + offsetY,
      confidence: value.confidence,
    },
  ])

  return Object.fromEntries(mappedEntries) as FaceAnchorSet
}

function getBundleSourceRect(
  image: HTMLImageElement,
) {
  return {
    x: 0,
    y: 0,
    w: image.naturalWidth,
    h: image.naturalHeight,
  }
}

export async function loadOverlayAssetBundle(
  asset: OverlayAssetSource,
): Promise<OverlayAssetBundle | null> {
  if (!asset.assetId || !asset.hairRgbaUrl || !asset.anchorsUrl) {
    return null
  }

  const cached = overlayBundleCache.get(asset.assetId)
  if (cached) {
    return cached
  }

  const inflight = overlayBundlePromiseCache.get(asset.assetId)
  if (inflight) {
    return inflight
  }

  const nextLoad = Promise.all([
    loadImage(asset.hairRgbaUrl),
    loadAssetAnchors(asset.anchorsUrl),
  ])
    .then(([image, anchorsPayload]) => {
      const bundle = {
        assetId: asset.assetId,
        image,
        anchors: anchorsPayload.anchors,
        hairBBox: asset.hairBBox,
      }
      overlayBundleCache.set(asset.assetId, bundle)
      return bundle
    })
    .finally(() => {
      overlayBundlePromiseCache.delete(asset.assetId)
    })

  overlayBundlePromiseCache.set(asset.assetId, nextLoad)
  return nextLoad
}

export function getCachedOverlayAssetBundle(assetId: string) {
  return overlayBundleCache.get(assetId) ?? null
}

function toOverlayAssetSource(
  asset: HairAssetIndexBundle,
): OverlayAssetSource {
  return {
    assetId: asset.assetId,
    hairRgbaUrl: asset.hairRgbaUrl,
    anchorsUrl: asset.anchorsUrl,
    hairBBox: asset.hairBBox,
  }
}

export async function preloadSessionOverlayAssets(
  staticBootstrap: HairApplyV2Response['static'],
  signal?: AbortSignal,
) {
  if (staticBootstrap.preloadAssetIds.length === 0) {
    return
  }

  const assetIndex = await fetchHairAssetIndex(
    staticBootstrap.assetIndexUrl,
    signal,
  )
  if (signal?.aborted) {
    return
  }

  const itemsById = new Map(
    assetIndex.items.map((item) => [item.assetId, item] as const),
  )
  const preloadTargets = staticBootstrap.preloadAssetIds
    .map((assetId) => itemsById.get(assetId))
    .filter((item): item is HairAssetIndexBundle => item != null)

  await Promise.allSettled(
    preloadTargets.map((item) => {
      if (signal?.aborted) {
        return Promise.resolve(null)
      }
      return loadOverlayAssetBundle(toOverlayAssetSource(item))
    }),
  )
}

function toCanvasMatrix(
  renderTask: InferenceRenderTask,
  sourceOrigin: Point,
  canvasWidth: number,
  canvasHeight: number,
  videoWidth: number,
  videoHeight: number,
): Matrix2D {
  const { scale, offsetX, offsetY } = getVideoCoverLayout(
    canvasWidth,
    canvasHeight,
    videoWidth,
    videoHeight,
  )

  const localMatrix = {
    a: renderTask.matrix.a,
    b: renderTask.matrix.b,
    c: renderTask.matrix.c,
    d: renderTask.matrix.d,
    e:
      renderTask.matrix.a * sourceOrigin.x +
      renderTask.matrix.c * sourceOrigin.y +
      renderTask.matrix.e,
    f:
      renderTask.matrix.b * sourceOrigin.x +
      renderTask.matrix.d * sourceOrigin.y +
      renderTask.matrix.f,
  }

  return {
    a: localMatrix.a * scale,
    b: localMatrix.b * scale,
    c: localMatrix.c * scale,
    d: localMatrix.d * scale,
    e: localMatrix.e * scale + offsetX,
    f: localMatrix.f * scale + offsetY,
  }
}

export function drawOverlayFrame({
  canvas,
  videoWidth,
  videoHeight,
  landmarks,
  bundle,
  renderTask,
}: {
  canvas: HTMLCanvasElement
  videoWidth: number
  videoHeight: number
  landmarks: NormalizedLandmark[]
  bundle: OverlayAssetBundle | null
  renderTask?: InferenceRenderTask | null
}) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.width
  const height = canvas.height
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, width, height)

  if (!bundle || landmarks.length === 0 || videoWidth <= 0 || videoHeight <= 0) {
    if (!bundle || videoWidth <= 0 || videoHeight <= 0) {
      return
    }
  }

  const sourceCrop = getBundleSourceRect(bundle.image)
  if (sourceCrop.w <= 0 || sourceCrop.h <= 0) {
    return
  }

  const sourceOrigin = {
    x: bundle.hairBBox?.x ?? 0,
    y: bundle.hairBBox?.y ?? 0,
  }

  const matrix = renderTask
    ? toCanvasMatrix(
        renderTask,
        sourceOrigin,
        width,
        height,
        videoWidth,
        videoHeight,
      )
    : (() => {
        if (landmarks.length === 0) {
          return null
        }

        const destinationAnchors = buildDestinationAnchors(
          landmarks,
          width,
          height,
          videoWidth,
          videoHeight,
        )
        const sourcePoints = getTransformPoints(bundle.anchors).map((point) =>
          shiftPoint(point, sourceOrigin.x, sourceOrigin.y),
        )
        const destinationPoints = getTransformPoints(destinationAnchors)

        return (
          estimateSimilarityTransform(sourcePoints, destinationPoints) ??
          estimateAffineFromThreePoints(
            sourcePoints.slice(0, 3),
            destinationPoints.slice(0, 3),
          )
        )
      })()

  if (!matrix) return

  ctx.save()
  ctx.setTransform(
    matrix.a,
    matrix.b,
    matrix.c,
    matrix.d,
    matrix.e,
    matrix.f,
  )
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(
    bundle.image,
    sourceCrop.x,
    sourceCrop.y,
    sourceCrop.w,
    sourceCrop.h,
    sourceCrop.x,
    sourceCrop.y,
    sourceCrop.w,
    sourceCrop.h,
  )
  ctx.restore()
}
