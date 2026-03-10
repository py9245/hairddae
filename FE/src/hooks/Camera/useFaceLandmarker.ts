import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision'
import { useEffect, useRef, useState } from 'react'

type Args = {
  enabled?: boolean
  wasmBaseUrl: string
  modelAssetPath: string
  numFaces?: number
}

export function useFaceLandmarker({
  enabled = true,
  wasmBaseUrl,
  modelAssetPath,
  numFaces = 1,
}: Args) {
  const landmarkerRef = useRef<FaceLandmarker | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!enabled) return

    let cancelled = false

    const init = async () => {
      try {
        const vision = await FilesetResolver.forVisionTasks(wasmBaseUrl)
        if (cancelled) return

        const landmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: { modelAssetPath },
          runningMode: 'VIDEO',
          numFaces,
          outputFacialTransformationMatrixes: true,
        })

        if (cancelled) {
          landmarker.close()
          return
        }

        landmarkerRef.current = landmarker
        setReady(true)
        setError(null)
      } catch (e) {
        setError(e)
        console.error('FaceLandmarker init failed:', e)
      }
    }

    init()

    return () => {
      cancelled = true
      setReady(false)
      if (landmarkerRef.current) {
        landmarkerRef.current.close()
        landmarkerRef.current = null
      }
    }
  }, [enabled, wasmBaseUrl, modelAssetPath, numFaces])

  return { landmarkerRef, ready, error }
}