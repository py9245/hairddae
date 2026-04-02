import { X } from 'lucide-react'

import { Button } from '@/components/ui/button'

type DesignerRequestDialogProps = {
  open: boolean
  imageUrl: string | null
  message: string
  isSubmitting?: boolean
  onClose: () => void
  onConfirm: () => void
  onMessageChange: (value: string) => void
}

export function DesignerRequestDialog({
  open,
  imageUrl,
  message,
  isSubmitting = false,
  onClose,
  onConfirm,
  onMessageChange,
}: DesignerRequestDialogProps) {
  if (!open) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="designer-request-dialog-title"
        className="relative flex w-full max-w-[380px] flex-col rounded-[24px] bg-white shadow-[0_20px_40px_rgba(15,23,42,0.18)]"
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="문의 전송 모달 닫기"
          className="absolute right-5 top-5 inline-flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black disabled:pointer-events-none"
          disabled={isSubmitting}
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex flex-col gap-5 px-6 pb-6 pt-6">
          <div className="space-y-2 pr-10">
            <h2
              id="designer-request-dialog-title"
              className="text-2xl font-bold leading-snug text-black"
            >
              시술 문의를
              <br />
              전송할까요?
            </h2>
            <p className="text-sm leading-6 text-gray-500">
              전송할 이미지와 메시지를 확인한 뒤 문의를 보내세요.
            </p>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-text-dark">
              전송할 이미지
            </p>
            <div className="overflow-hidden rounded-[20px] border border-black/8 bg-[#f7f5f2]">
              {imageUrl ? (
                <img
                  src={imageUrl}
                  alt="전송할 시술 이미지"
                  className="h-[180px] w-full object-cover"
                />
              ) : (
                <div className="flex h-[180px] items-center justify-center px-6 text-sm text-text-sub">
                  전송할 이미지를 불러오지 못했습니다.
                </div>
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-text-dark">
                문의 메시지
              </p>
              <span className="text-xs text-text-sub">수정 가능</span>
            </div>
            <textarea
              value={message}
              onChange={(event) => onMessageChange(event.target.value)}
              rows={4}
              className="min-h-[124px] w-full resize-none rounded-[20px] border border-black/8 bg-[#faf8f5] px-4 py-3 text-sm leading-6 text-text-dark outline-none transition placeholder:text-text-sub focus:border-primary-200"
              placeholder="문의 메시지를 입력해 주세요."
              disabled={isSubmitting}
            />
          </div>

          <div className="rounded-[20px] bg-[#f7f4ee] px-4 py-3 text-sm leading-6 text-text-sub">
            이 내용으로 전송할까요?
          </div>

          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="outline"
              className="h-12 flex-1 rounded-xl border-gray-200 text-base font-medium text-gray-600 hover:bg-gray-50"
              onClick={onClose}
              disabled={isSubmitting}
            >
              취소
            </Button>
            <Button
              type="button"
              variant="login"
              className="h-12 flex-1 rounded-xl text-base font-medium"
              onClick={onConfirm}
              disabled={isSubmitting || message.trim() === ''}
            >
              {isSubmitting ? '전송 중...' : '전송하기'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
