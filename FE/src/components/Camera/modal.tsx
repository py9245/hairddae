import { X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type ApplyStyleModalContent = {
  title: string
  tips: string[]
}

const mockModalContent: ApplyStyleModalContent = {
  title: '선택한 스타일을 적용하고 있어요.',
  tips: [
    '얼굴이 길어 보인다면 구레나룻을',
    '너무 짧게 치지 마세요.',
    '옆 볼륨이 살아야 시선이 분산됩니다.',
  ],
}

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
  content = mockModalContent,
  scale = 1,
}: ApplyStyleModalProps) {
  const [progress, setProgress] = useState(0)
  const [failed, setFailed] = useState(false)
  const finishedRef = useRef(false)

  useEffect(() => {
    if (!open) {
      setProgress(0)
      setFailed(false)
      finishedRef.current = false
      return
    }
  }, [open])

  useEffect(() => {
    if (!open || failed) return

    if (completed) {
      const timer = window.setInterval(() => {
        setProgress((prev) => {
          const next = Math.min(prev + 10, 100)

          if (next >= 100 && !finishedRef.current) {
            finishedRef.current = true
            window.clearInterval(timer)
            window.setTimeout(() => {
              onFinish?.()
            }, 120)
          }

          return next
        })
      }, 40)

      return () => {
        window.clearInterval(timer)
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
    }, 5000)

    return () => {
      window.clearTimeout(timer)
    }
  }, [open, completed, failed, progress])

  if (!open) return null

  return (
    <div
      className="origin-center"
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
              {failed ? '적용에 실패했어요.' : content.title}
            </h2>

            {failed ? (
              <div className="space-y-1 text-sm leading-snug text-gray-500">
                <p>네트워크 상태를 확인한 뒤 다시 시도해 주세요.</p>
                <p>문제가 계속되면 스타일을 다시 선택해 주세요.</p>
              </div>
            ) : (
              <div className="space-y-1 text-sm leading-snug text-gray-500">
                {content.tips.map((tip) => (
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
