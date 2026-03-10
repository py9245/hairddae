import { useEffect, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Field, FieldLabel } from '@/components/ui/field'
import { Progress } from '@/components/ui/progress'

function ProgressWithLabel({ value }: { value: number }) {
  return (
    <Field className="w-full space-y-2">
      <FieldLabel
        htmlFor="progress-upload"
        className="flex items-center text-sm font-medium text-zinc-700"
      >
        <span>적용 진행률</span>
        <span className="ml-auto text-zinc-500">{value}%</span>
      </FieldLabel>

      <Progress
        value={value}
        id="progress-upload"
        className="h-3 rounded-full"
      />
    </Field>
  )
}

export function Modal({
  open,
  targetLabel,
  onComplete,
}: {
  open: boolean
  targetLabel?: string
  onComplete: () => void
}) {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    if (!open) {
      setProgress(0)
      return
    }

    const duration = 3000
    const intervalMs = 50
    const totalSteps = duration / intervalMs
    let currentStep = 0

    const timer = setInterval(() => {
      currentStep += 1
      const next = Math.min(100, Math.round((currentStep / totalSteps) * 100))
      setProgress(next)

      if (next >= 100) {
        clearInterval(timer)
        onComplete()
      }
    }, intervalMs)

    return () => clearInterval(timer)
  }, [open, onComplete])

  return (
    <Dialog open={open}>
      <DialogContent className="sm:max-w-md overflow-hidden rounded-2xl border-0 p-0 shadow-2xl [&>button]:hidden">
        <div className="bg-gradient-to-b from-zinc-50 to-white px-6 py-6">
          <DialogHeader className="space-y-3 text-left">
            <DialogTitle className="text-xl font-semibold text-zinc-900">
              헤어 적용 중...
            </DialogTitle>
          </DialogHeader>

          <div className="mt-5 space-y-5">
            <div className="rounded-2xl bg-zinc-100/80 px-4 py-4 text-sm leading-6 text-zinc-700">
              <div className="font-medium text-zinc-900">선택한 스타일</div>
              <div className="mt-1">{targetLabel ?? '헤어 스타일 적용 중'}</div>
            </div>

            <ProgressWithLabel value={progress} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
