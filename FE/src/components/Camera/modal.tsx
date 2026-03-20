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
  content?: ApplyStyleModalContent
}

export function ApplyStyleModal({
  open,
  completed = false,
  onFinish,
  content = mockModalContent,
}: ApplyStyleModalProps) {
  const [progress, setProgress] = useState(0)
  const finishedRef = useRef(false)

  useEffect(() => {
    if (!open) {
      setProgress(0)
      finishedRef.current = false
      return
    }

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
  }, [open, completed, onFinish])

  if (!open) return null

  return (
    <div className="w-[380px] max-w-[calc(100%-32px)] rounded-[24px] bg-white p-0 shadow-none">
      <div className="px-6 py-6">
        <div className="space-y-5">
          <h2 className="text-xl font-bold leading-snug text-black">
            {content.title}
          </h2>

          <div className="space-y-1 text-sm leading-snug text-gray-500">
            {content.tips.map((tip) => (
              <p key={tip}>{tip}</p>
            ))}
          </div>

          <div className="pt-1">
            <ProgressBar value={progress} />
          </div>
        </div>
      </div>
    </div>
  )
}
