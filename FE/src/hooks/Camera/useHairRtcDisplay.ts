import { type RefObject, useEffect, useRef, useState } from 'react'

import { describeMediaStream, logRtcDebug } from '@/lib/Camera/debug'

type RemoteVideoSize = {
  width: number
  height: number
}

type UseHairRtcDisplayArgs = {
  localVideoRef: RefObject<HTMLVideoElement | null>
  remoteStream: MediaStream | null
  isRenderReady: boolean
  settleMs?: number
}

export function useHairRtcDisplay({
  localVideoRef,
  remoteStream,
  isRenderReady,
  settleMs = 40,
}: UseHairRtcDisplayArgs) {
  const remoteVideoRef = useRef<HTMLVideoElement | null>(null)

  const [remoteVideoReady, setRemoteVideoReady] = useState(false)
  const [remoteDisplayReady, setRemoteDisplayReady] = useState(false)
  const [remoteVideoSize, setRemoteVideoSize] =
    useState<RemoteVideoSize | null>(null)

  const hasRemoteVideo = remoteDisplayReady

  useEffect(() => {
    const remoteVideo = remoteVideoRef.current
    if (!remoteVideo) return

    logRtcDebug('remote display stream update', {
      remoteStream: describeMediaStream(remoteStream),
    })
    setRemoteVideoReady(false)
    setRemoteVideoSize(null)
    remoteVideo.srcObject = remoteStream

    if (!remoteStream) {
      return () => {
        remoteVideo.srcObject = null
      }
    }

    const markReady = () => {
      if (remoteVideo.videoWidth <= 0 || remoteVideo.videoHeight <= 0) return

      setRemoteVideoReady(true)
      setRemoteVideoSize({
        width: remoteVideo.videoWidth,
        height: remoteVideo.videoHeight,
      })
    }

    const markWaiting = () => {
      setRemoteVideoReady(false)
      setRemoteVideoSize(null)
    }

    remoteVideo.addEventListener('loadedmetadata', markReady)
    remoteVideo.addEventListener('loadeddata', markReady)
    remoteVideo.addEventListener('playing', markReady)
    remoteVideo.addEventListener('resize', markReady)
    remoteVideo.addEventListener('emptied', markWaiting)

    if (remoteStream.getVideoTracks().length > 0) {
      void remoteVideo.play().catch(() => {})
    }

    return () => {
      remoteVideo.removeEventListener('loadedmetadata', markReady)
      remoteVideo.removeEventListener('loadeddata', markReady)
      remoteVideo.removeEventListener('playing', markReady)
      remoteVideo.removeEventListener('resize', markReady)
      remoteVideo.removeEventListener('emptied', markWaiting)
      setRemoteVideoReady(false)
      setRemoteVideoSize(null)
      remoteVideo.srcObject = null
    }
  }, [remoteStream])

  useEffect(() => {
    if (!remoteVideoReady || !isRenderReady) {
      setRemoteDisplayReady(false)
      return
    }

    const timeoutId = window.setTimeout(() => {
      setRemoteDisplayReady(true)
    }, settleMs)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [isRenderReady, remoteVideoReady, settleMs])

  useEffect(() => {
    logRtcDebug('remote display readiness changed', {
      remoteVideoReady,
      remoteDisplayReady,
      hasRemoteVideo,
      isRenderReady,
      remoteVideoSize,
    })
  }, [
    hasRemoteVideo,
    isRenderReady,
    remoteDisplayReady,
    remoteVideoReady,
    remoteVideoSize,
  ])

  useEffect(() => {
    const displayVideo = hasRemoteVideo
      ? remoteVideoRef.current
      : localVideoRef.current
    if (!displayVideo) return

    logRtcDebug('display video play requested', {
      source: hasRemoteVideo ? 'remote' : 'local',
    })
    void displayVideo.play().catch(() => {})
  }, [hasRemoteVideo, localVideoRef])

  return {
    remoteVideoRef,
    remoteVideoReady,
    remoteDisplayReady,
    remoteVideoSize,
    hasRemoteVideo,
  }
}
