import { CheckCircle2, LoaderCircle, X } from 'lucide-react'

import { Button } from '@/components/ui/button'

type CaptureCompleteModalProps = {
  open: boolean
  onClose: () => void
  onFindDesigner: () => void
  onAiEnhance: () => void
  aiEnhancePending?: boolean
  aiEnhanceMessage?: string | null
  scale?: number
}

export function CaptureCompleteModal({
  open,
  onClose,
  onFindDesigner,
  onAiEnhance,
  aiEnhancePending = false,
  aiEnhanceMessage = null,
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
      <div className="relative w-[380px] rounded-[24px] bg-white p-6 text-text-dark shadow-[0_24px_80px_rgba(2,6,23,0.24)]">
        <button
          type="button"
          onClick={onClose}
          aria-label="캡처 완료 모달 닫기"
          className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black"
          disabled={aiEnhancePending}
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
            다음 작업을 선택해 계속 진행해 보세요.
          </p>

          {aiEnhancePending ? (
            <div className="mt-6 flex flex-col items-center gap-3">
              <LoaderCircle
                className="h-8 w-8 animate-spin text-primary-300"
                aria-hidden="true"
              />
              <p className="text-base font-semibold text-text-dark">
                AI 보정중...
              </p>
              {aiEnhanceMessage ? (
                <p className="text-sm leading-6 text-text-warm-400">
                  {aiEnhanceMessage}
                </p>
              ) : null}
            </div>
          ) : (
            <>
              {aiEnhanceMessage ? (
                <p className="mt-4 text-sm leading-6 text-text-warm-400">
                  {aiEnhanceMessage}
                </p>
              ) : null}

              <div className="mt-6 flex w-full flex-col gap-3">
                <Button variant="login" size="full" onClick={onFindDesigner}>
                  디자이너 찾기
                </Button>
                <Button
                  variant="outline"
                  size="full"
                  className="text-text-dark"
                  onClick={onAiEnhance}
                >
                  AI 보정하기
                </Button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
