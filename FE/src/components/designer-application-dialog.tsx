import { useMutation } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Field, FieldError, FieldGroup, FieldLabel } from '@/components/ui/field'
import {
  submitDesignerApplication,
  type DesignerApplicationRequest,
} from '@/lib/mypage'

type DesignerApplicationDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type DesignerApplicationForm = {
  certificateNumber: string
  salonAddress: string
}

const INITIAL_FORM: DesignerApplicationForm = {
  certificateNumber: '',
  salonAddress: '',
}

export function DesignerApplicationDialog({
  open,
  onOpenChange,
}: DesignerApplicationDialogProps) {
  const [form, setForm] = useState<DesignerApplicationForm>(INITIAL_FORM)
  const [submitAttempted, setSubmitAttempted] = useState(false)

  const mutation = useMutation({
    mutationFn: (payload: DesignerApplicationRequest) =>
      submitDesignerApplication(payload),
  })

  useEffect(() => {
    if (open) {
      return
    }

    setForm(INITIAL_FORM)
    setSubmitAttempted(false)
    mutation.reset()
  }, [open, mutation])

  if (!open) {
    return null
  }

  const certificateNumber = form.certificateNumber.trim()
  const salonAddress = form.salonAddress.trim()
  const isFormValid = certificateNumber !== '' && salonAddress !== ''
  const certificateNumberError =
    submitAttempted && !certificateNumber
      ? '자격증 번호를 입력해 주세요.'
      : null
  const salonAddressError =
    submitAttempted && !salonAddress ? '미용실 주소를 입력해 주세요.' : null

  function handleChange<K extends keyof DesignerApplicationForm>(
    key: K,
    value: DesignerApplicationForm[K],
  ) {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }))
  }

  function handleClose() {
    if (mutation.isPending) {
      return
    }

    onOpenChange(false)
  }

  function handleSubmit() {
    setSubmitAttempted(true)

    if (!isFormValid) {
      return
    }

    mutation.mutate({
      certificateNumber,
      salonAddress,
    })
  }

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="designer-application-title"
        className="pointer-events-auto w-full max-w-[360px] rounded-[24px] bg-card p-6 shadow-[0_20px_40px_rgba(15,23,42,0.18)]"
      >
        {mutation.isSuccess ? (
          <div className="space-y-5">
            <div className="space-y-2 text-left">
              <h2
                id="designer-application-title"
                className="text-xl font-bold text-text-warm-600"
              >
                디자이너 신청 완료
              </h2>
              <p className="text-sm leading-6 text-text-warm-400">
                {mutation.data.message}
              </p>
            </div>
            <Button variant="login" size="full" onClick={() => onOpenChange(false)}>
              닫기
            </Button>
          </div>
        ) : (
          <div className="space-y-5">
            <div className="relative pr-10 text-left">
              <button
                type="button"
                aria-label="디자이너 신청 모달 닫기"
                className="absolute -right-1 -top-1 inline-flex h-9 w-9 items-center justify-center rounded-full text-text-warm-400 transition hover:bg-neutral-100 hover:text-text-dark"
                onClick={handleClose}
                disabled={mutation.isPending}
              >
                <X className="h-5 w-5" />
              </button>
              <h2
                id="designer-application-title"
                className="text-xl font-bold text-text-warm-600"
              >
                디자이너 신청
              </h2>
              <p className="mt-2 text-sm leading-6 text-text-warm-400">
                자격증 번호와 미용실 주소를 입력한 뒤 신청해 주세요.
              </p>
            </div>

            <FieldGroup className="gap-4">
              <Field>
                <FieldLabel
                  htmlFor="designer-certificate-number"
                  className="text-sm font-semibold text-text-dark"
                >
                  자격증 번호
                </FieldLabel>
                <input
                  id="designer-certificate-number"
                  type="text"
                  value={form.certificateNumber}
                  onChange={(event) =>
                    handleChange('certificateNumber', event.target.value)
                  }
                  placeholder="자격증 번호를 입력해 주세요"
                  className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
                  disabled={mutation.isPending}
                />
                <FieldError>{certificateNumberError}</FieldError>
              </Field>

              <Field>
                <FieldLabel
                  htmlFor="designer-salon-address"
                  className="text-sm font-semibold text-text-dark"
                >
                  미용실 위치
                </FieldLabel>
                <input
                  id="designer-salon-address"
                  type="text"
                  value={form.salonAddress}
                  onChange={(event) =>
                    handleChange('salonAddress', event.target.value)
                  }
                  placeholder="주소를 입력해 주세요"
                  className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
                  disabled={mutation.isPending}
                />
                <FieldError>{salonAddressError}</FieldError>
              </Field>
            </FieldGroup>

            {mutation.isError ? (
              <p className="text-sm text-error" role="alert">
                {mutation.error instanceof Error
                  ? mutation.error.message
                  : '디자이너 신청 중 오류가 발생했습니다.'}
              </p>
            ) : null}

            <div className="flex gap-2">
              <Button
                variant="outline"
                className="h-12 flex-1 rounded-xl"
                onClick={handleClose}
                disabled={mutation.isPending}
              >
                취소
              </Button>
              <Button
                variant="login"
                className="h-12 flex-1 rounded-xl"
                onClick={handleSubmit}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? '신청 중...' : '신청하기'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
