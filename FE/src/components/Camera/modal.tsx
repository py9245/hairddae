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

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-3 w-full rounded-full bg-gray-300 p-[2px]">
      <div
        className="h-full rounded-full bg-rose-200 transition-all duration-300"
        style={{ width: `${value}%` }}
      />
    </div>
  )
}

export function ApplyStyleModal({
  open,
  onComplete,
  content = mockModalContent,
}: {
  open: boolean
  onComplete: () => void
  content?: ApplyStyleModalContent
}) {
  const [progress, setProgress] = useState(0)
  const onCompleteRef = useRef(onComplete)

  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  useEffect(() => {
    if (!open) {
      setProgress(0)
      return
    }

    const duration = 100
    const intervalMs = 50
    const totalSteps = duration / intervalMs
    let currentStep = 0

    const timer = setInterval(() => {
      currentStep += 1
      const next = Math.min(100, Math.round((currentStep / totalSteps) * 100))
      setProgress(next)

      if (next >= 100) {
        clearInterval(timer)
        onCompleteRef.current()
      }
    }, intervalMs)

    return () => clearInterval(timer)
  }, [open])

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
