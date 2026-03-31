import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import {
  type DesignerApplicationRequest,
  submitDesignerApplication,
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

  const certificateNumber = form.certificateNumber.trim()
  const salonAddress = form.salonAddress.trim()
  const certificateNumberError =
    submitAttempted && !certificateNumber
      ? '자격증 번호를 입력해 주세요.'
      : null
  const salonAddressError =
    submitAttempted && !salonAddress ? '미용실 주소를 입력해 주세요.' : null
  const isFormValid = certificateNumber !== '' && salonAddress !== ''

  function handleChange<K extends keyof DesignerApplicationForm>(
    key: K,
    value: DesignerApplicationForm[K],
  ) {
    setForm((prev) => ({
      ...prev,
      [key]: value,
    }))
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={!mutation.isPending}
        className="max-w-[360px] rounded-[24px] border-none bg-card p-6"
      >
        {mutation.isSuccess ? (
          <>
            <DialogHeader className="gap-3 text-left">
              <DialogTitle className="text-xl font-bold text-text-warm-600">
                디자이너 신청 완료
              </DialogTitle>
              <DialogDescription className="text-sm leading-6 text-text-warm-400">
                {mutation.data.message}
              </DialogDescription>
            </DialogHeader>

            <DialogFooter className="mt-2">
              <Button
                variant="login"
                size="full"
                onClick={() => onOpenChange(false)}
              >
                닫기
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader className="gap-2 text-left">
              <DialogTitle className="text-xl font-bold text-text-warm-600">
                디자이너 신청
              </DialogTitle>
              <DialogDescription className="text-sm leading-6 text-text-warm-400">
                자격증 번호와 미용실 주소를 입력한 뒤 신청해 주세요.
              </DialogDescription>
            </DialogHeader>

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
                  미용실 주소
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

            <DialogFooter className="mt-2">
              <Button
                variant="outline"
                className="h-12 rounded-xl"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                취소
              </Button>
              <Button
                variant="login"
                className="h-12 rounded-xl"
                onClick={handleSubmit}
                disabled={mutation.isPending}
              >
                {mutation.isPending ? '신청 중...' : '신청하기'}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
