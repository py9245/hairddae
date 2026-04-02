import { X } from 'lucide-react'

type GuideModalProps = {
  open: boolean
  onClose: () => void
  onDismiss: () => void
  scale?: number
}

export function GuideModal({
  open,
  onClose,
  onDismiss,
  scale = 1,
}: GuideModalProps) {
  if (!open) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="pointer-events-auto origin-center"
      style={{
        transform: `scale(${scale})`,
      }}
    >
      <div className="relative flex w-[380px] min-h-[240px] flex-col rounded-[16px] bg-white p-0 shadow-none">
        <div className="flex-1 px-6 pb-6 pt-6">
          <div className="space-y-5">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-2xl font-bold leading-snug text-black">
                  더 완벽한 피팅을 <br />
                  위해 확인해 주세요
                </h2>

                <button
                  type="button"
                  onClick={onClose}
                  aria-label="가이드 닫기"
                  className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:text-[var(--color-primary-300)]"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-1 pl-2 text-base leading-snug text-gray-500">
                <p className="pl-4 -indent-4">
                  1.{' '}
                  <span className="font-bold text-[var(--color-primary-200)]">
                    이마
                  </span>
                  가 보이면 좋아요.
                </p>
                <p className="pl-4 -indent-4">
                  2.{' '}
                  <span className="font-bold text-[var(--color-primary-200)]">
                    귀
                  </span>
                  가 보이면 좋아요.
                </p>
                <p className="pl-4 -indent-4">
                  3.{' '}
                  <span className="font-bold text-[var(--color-primary-200)]">
                    머리
                  </span>
                  를{' '}
                  <span className="font-bold text-[var(--color-primary-200)]">
                    뒤
                  </span>
                  로 넘기면 좋아요.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <div className="overflow-hidden rounded-2xl border border-gray-200 bg-gray-50">
                  <img
                    src="/guide/images/bad-case.svg"
                    alt="잘못된 촬영 예시"
                    className="h-auto w-full object-cover"
                  />
                </div>
                <p className="text-center text-sm font-semibold text-[var(--color-error)]">
                  헤어를 입히기 어려워요
                </p>
              </div>

              <div className="space-y-2">
                <div className="overflow-hidden rounded-2xl border border-gray-200 bg-gray-50">
                  <img
                    src="/guide/images/good-case.svg"
                    alt="올바른 촬영 예시"
                    className="h-auto w-full object-cover"
                  />
                </div>
                <p className="text-center text-sm font-semibold text-[var(--color-text-good)]">
                  헤어를 입히기 딱 좋아요
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex justify-start px-6 pb-6">
          <button
            type="button"
            onClick={onDismiss}
            className="text-sm font-medium text-gray-400 transition hover:text-[var(--color-primary-300)]"
          >
            다시보지 않기
          </button>
        </div>
      </div>
    </div>
  )
}
