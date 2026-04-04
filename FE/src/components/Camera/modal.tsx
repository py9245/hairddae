import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type ApplyStyleModalContent = {
  title: string
  tips: string[]
}

const mockModalContents: ApplyStyleModalContent[] = [
  {
    title: '선택한 스타일을 적용하고 있어요',
    tips: [
      '정면을 보고 있으면 결과가 더 안정적이에요.',
      '머리카락이 얼굴을 가리지 않게 정리해 주세요.',
      '화면 안에서 천천히 움직여 주세요.',
    ],
  },
  {
    title: '새 헤어 스타일을 준비 중이에요',
    tips: [
      '고개를 너무 빠르게 돌리면 추적이 흔들릴 수 있어요.',
      '이마와 턱선이 보이면 인식이 더 쉬워져요.',
      '밝은 곳에서 사용하면 결과가 더 자연스러워요.',
    ],
  },
  {
    title: '지금 스타일을 맞추고 있어요',
    tips: [
      '카메라와 얼굴 사이 거리를 조금만 유지해 주세요.',
      '모자나 굵은 액세서리는 잠시 벗어 두면 좋아요.',
      '정면에서 시작하면 적용 속도가 더 빨라져요.',
    ],
  },
  {
    title: '헤어 효과를 반영하는 중이에요',
    tips: [
      '머리 윤곽이 잘 보이도록 배경과 구분해 주세요.',
      '머리 전체가 화면 안에 들어오면 더 정확해져요.',
      '잠깐만 기다리면 스타일이 곧 반영돼요.',
    ],
  },
  {
    title: '어울리는 스타일을 씌우는 중이에요',
    tips: [
      '카메라를 손으로 크게 흔들지 않는 편이 좋아요.',
      '측면보다는 정면 각도에서 먼저 확인해 보세요.',
      '적용 후 캡처하면 현재 스타일로 저장할 수 있어요.',
    ],
  },
]

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-3 w-full rounded-full bg-gray-300 p-[2px]">
      <div
        className="h-full transition-all duration-300"
        style={{
          width: `${value}%`,
          borderRadius: '30px',
          background: 'var(--primary-gradient)',
        }}
      />
    </div>
  )
}

type ApplyStyleModalProps = {
  open: boolean
  completed?: boolean
  onFinish?: () => void
  onClose?: () => void
  content?: ApplyStyleModalContent
  scale?: number
}

export function ApplyStyleModal({
  open,
  completed = false,
  onFinish,
  onClose,
  content,
  scale = 1,
}: ApplyStyleModalProps) {
  const [progress, setProgress] = useState(0)
  const [failed, setFailed] = useState(false)
  const [randomContent, setRandomContent] = useState<ApplyStyleModalContent>(
    mockModalContents[0],
  )
  const finishedRef = useRef(false)
  const completionStartRef = useRef<number | null>(null)
  const progressRef = useRef(0)

  const modalContent = content ?? randomContent

  useEffect(() => {
    progressRef.current = progress
  }, [progress])

  useEffect(() => {
    if (!open) {
      setProgress(0)
      setFailed(false)
      finishedRef.current = false
      completionStartRef.current = null
      progressRef.current = 0
      return
    }

    if (!content) {
      const randomIndex = Math.floor(Math.random() * mockModalContents.length)
      setRandomContent(mockModalContents[randomIndex])
    }
  }, [content, open])

  useEffect(() => {
    if (!open || failed) return

    if (completed) {
      if (completionStartRef.current == null) {
        completionStartRef.current = performance.now()
      }

      const startAt = completionStartRef.current
      const startProgress = progressRef.current
      const COMPLETE_DURATION_MS = 480
      let frameId = 0

      const tick = () => {
        const elapsed = performance.now() - startAt
        const ratio = Math.min(elapsed / COMPLETE_DURATION_MS, 1)
        const next = Math.min(
          100,
          startProgress + (100 - startProgress) * ratio,
        )

        setProgress(next)

        if (ratio >= 1) {
          if (!finishedRef.current) {
            finishedRef.current = true
            window.setTimeout(() => {
              onFinish?.()
            }, 120)
          }
          return
        }

        frameId = window.requestAnimationFrame(tick)
      }

      frameId = window.requestAnimationFrame(tick)

      return () => {
        window.cancelAnimationFrame(frameId)
      }
    }

    const timer = window.setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) return prev
        return Math.min(prev + 5, 90)
      })
    }, 120)

    return () => {
      window.clearInterval(timer)
    }
  }, [open, completed, failed, onFinish])

  useEffect(() => {
    if (!open || completed || failed || progress < 90) return

    const timer = window.setTimeout(() => {
      setFailed(true)
    }, 10000)

    return () => {
      window.clearTimeout(timer)
    }
  }, [open, completed, failed, progress])

  if (!open) return null

  return (
    <div
      data-testid="apply-style-modal"
      className="pointer-events-auto origin-center"
      style={{
        transform: `scale(${scale})`,
      }}
    >
      <div className="relative w-[380px] rounded-[24px] bg-white p-0 shadow-none">
        {failed && (
          <button
            type="button"
            onClick={onClose}
            aria-label="모달 닫기"
            className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black"
          >
            <X className="h-5 w-5" />
          </button>
        )}

        <div className="px-6 py-6">
          <div className="space-y-5">
            <h2 className="pr-10 text-xl font-bold leading-snug text-black">
              {failed ? '적용에 실패했어요' : modalContent.title}
            </h2>

            {failed ? (
              <div className="space-y-1 text-sm leading-snug text-gray-500">
                <p>네트워크 상태를 확인한 뒤 다시 시도해 주세요.</p>
                <p>문제가 계속되면 스타일을 다시 선택해 주세요.</p>
              </div>
            ) : (
              <div className="space-y-1 text-sm leading-snug text-gray-500">
                {modalContent.tips.map((tip) => (
                  <p key={tip}>{tip}</p>
                ))}
              </div>
            )}

            <div className="pt-1">
              <ProgressBar value={progress} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

type CameraNoticeModalProps = {
  open: boolean
  title: string
  description: string[]
  confirmLabel?: string
  onConfirm: () => void
  onClose?: () => void
  scale?: number
}

export function CameraNoticeModal({
  open,
  title,
  description,
  confirmLabel = '메인으로 이동',
  onConfirm,
  onClose,
  scale = 1,
}: CameraNoticeModalProps) {
  if (!open) return null

  return (
    <div
      className="origin-center"
      style={{
        transform: `scale(${scale})`,
      }}
    >
      <div className="relative w-[380px] rounded-[24px] bg-white p-0 shadow-none">
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="모달 닫기"
            className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black"
          >
            <X className="h-5 w-5" />
          </button>
        ) : null}

        <div className="space-y-6 px-6 py-6">
          <div className="space-y-2">
            <h2 className="pr-10 text-xl font-bold leading-snug text-black">
              {title}
            </h2>

            <div className="space-y-1 text-sm leading-snug text-gray-500">
              {description.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </div>

          <button
            type="button"
            onClick={onConfirm}
            className="h-12 w-full rounded-xl bg-primary-300 px-6 text-base font-medium text-neutral-100 transition hover:bg-primary-hover"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
