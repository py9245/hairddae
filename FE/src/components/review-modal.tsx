import { ExternalLink, X } from 'lucide-react'

type ReviewModalProps = {
  open: boolean
  onClose: () => void
  onDefer?: () => void
  onSubmit?: () => void
  scale?: number
}

const REVIEW_FORM_URL = 'https://forms.gle/9EfwJtZjE3ZwFTRo9'

export function ReviewModal({
  open,
  onClose,
  onDefer,
  onSubmit,
  scale = 1,
}: ReviewModalProps) {
  if (!open) return null

  const handleOpenReviewForm = () => {
    onSubmit?.()
    window.open(REVIEW_FORM_URL, '_blank', 'noopener,noreferrer')
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-modal-title"
      className="pointer-events-auto origin-center"
      style={{
        transform: `scale(${scale})`,
      }}
    >
      <div className="relative flex w-[380px] min-h-[260px] flex-col rounded-[12px] bg-white p-0 shadow-none">
        <button
          type="button"
          onClick={onClose}
          aria-label="후기 모달 닫기"
          className="absolute right-5 top-5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-black"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex-1 px-6 pb-6 pt-6">
          <div className="space-y-5">
            <div className="space-y-3">
              <h2
                id="review-modal-title"
                className="pr-10 text-2xl font-bold leading-snug text-black"
              >
                여려분의 소중한
                <br />
                후기를 들려주세요
              </h2>

              <div className="space-y-1 text-base leading-snug text-gray-500">
                <p>짧은 설문으로 서비스 경험을 남겨주실 수 있어요.</p>
                <p> 들려주신 이야기로 더 자연스럽고</p>
                <p>완벽한 헤어때를 만들어갈게요.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 px-6 pb-6">
          <button
            type="button"
            onClick={onDefer ?? onClose}
            className="h-12 flex-1 rounded-xl border border-gray-200 px-4 text-base font-medium text-gray-600 transition hover:bg-gray-50"
          >
            나중에
          </button>
          <button
            type="button"
            onClick={handleOpenReviewForm}
            className="inline-flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-primary-300 px-4 text-base font-medium text-neutral-100 transition hover:bg-primary-hover"
          >
            후기 남기기
            <ExternalLink className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
