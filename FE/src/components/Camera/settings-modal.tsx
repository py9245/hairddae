import { X } from 'lucide-react'

type CameraSettingsModalProps = {
  open: boolean
  mirrored: boolean
  onMirroredChange: (value: boolean) => void
  onClose: () => void
  scale?: number
}

export function CameraSettingsModal({
  open,
  mirrored,
  onMirroredChange,
  onClose,
  scale = 1,
}: CameraSettingsModalProps) {
  if (!open) return null

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/35 px-4">
      <div
        className="origin-center"
        style={{
          transform: `scale(${scale})`,
        }}
      >
        <div className="w-[340px] rounded-[24px] border border-white/10 bg-black/70 p-5 shadow-2xl backdrop-blur-md">
          <div className="mb-5 flex items-center justify-between gap-3">
            <h2 className="text-xl font-semibold text-white">설정</h2>

            <button
              type="button"
              onClick={onClose}
              aria-label="설정 닫기"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white/80 transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="rounded-2xl px-4 py-4">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0 pr-2">
                <p className="text-base font-medium text-white">좌우반전</p>
                <p className="mt-1 break-keep text-sm leading-snug text-white/65">
                  카메라 화면을 거울처럼 보여줘요.
                </p>
              </div>

              <button
                type="button"
                role="switch"
                aria-checked={mirrored}
                onClick={() => {
                  onMirroredChange(!mirrored)
                }}
                className={[
                  'relative inline-flex h-8 w-14 shrink-0 items-center rounded-full transition',
                  mirrored ? 'bg-white' : 'bg-white/20',
                ].join(' ')}
              >
                <span
                  className={[
                    'inline-block h-6 w-6 rounded-full transition',
                    mirrored
                      ? 'translate-x-7 bg-black'
                      : 'translate-x-1 bg-white',
                  ].join(' ')}
                />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
