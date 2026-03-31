import { CheckCircle2, X } from 'lucide-react'

import { Button } from '@/components/ui/button'

type CaptureCompleteModalProps = {
  open: boolean
  onClose: () => void
  scale?: number
}

export function CaptureCompleteModal({
  open,
  onClose,
  scale = 1,
}: CaptureCompleteModalProps) {
  if (!open) {
    return null
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="capture-complete-title"
      className="pointer-events-auto origin-center"
      style={{
        transform: `scale(${scale})`,
      }}
    >
      <div className="relative w-[380px] rounded-[24px] bg-white p-6 shadow-[0_24px_80px_rgba(2,6,23,0.24)]">
        <button
          type="button"
          onClick={onClose}
          aria-label="캡처 완료 모달 닫기"
          className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary-50 text-primary-300">
            <CheckCircle2 className="h-7 w-7" />
          </div>

          <h2
            id="capture-complete-title"
            className="mt-4 text-xl font-bold text-text-dark"
          >
            캡처가 완료되었어요
          </h2>

          <p className="mt-2 text-sm leading-6 text-text-warm-400">
            현재 스타일 이미지가 저장되었어요.
            <br />
            마음에 드는 스타일을 다시 캡처해 비교해 보세요.
          </p>

          <Button
            variant="login"
            size="full"
            className="mt-6"
            onClick={onClose}
          >
            확인
          </Button>
        </div>
      </div>
    </div>
  )
}
