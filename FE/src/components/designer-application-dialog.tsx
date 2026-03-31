import { useMutation } from '@tanstack/react-query'
import { MapPin, Search, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
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

type KakaoPostcodeData = {
  roadAddress: string
  jibunAddress: string
  zonecode: string
  buildingName?: string
}

declare global {
  interface Window {
    kakao?: {
      Postcode: new (options: {
        oncomplete: (data: KakaoPostcodeData) => void
      }) => {
        open: () => void
      }
    }
    __kakaoPostcodeLoader__?: Promise<void>
  }
}

const INITIAL_FORM: DesignerApplicationForm = {
  certificateNumber: '',
  salonAddress: '',
}

const KAKAO_POSTCODE_SCRIPT_URL =
  'https://t1.kakaocdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js'

function loadKakaoPostcodeScript() {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('브라우저 환경이 아닙니다.'))
  }

  if (window.kakao?.Postcode) {
    return Promise.resolve()
  }

  if (window.__kakaoPostcodeLoader__) {
    return window.__kakaoPostcodeLoader__
  }

  window.__kakaoPostcodeLoader__ = new Promise<void>((resolve, reject) => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      `script[src="${KAKAO_POSTCODE_SCRIPT_URL}"]`,
    )

    const handleLoad = () => resolve()
    const handleError = () => {
      window.__kakaoPostcodeLoader__ = undefined
      reject(new Error('카카오 주소 검색 스크립트를 불러오지 못했습니다.'))
    }

    if (existingScript) {
      existingScript.addEventListener('load', handleLoad, { once: true })
      existingScript.addEventListener('error', handleError, { once: true })
      return
    }

    const script = document.createElement('script')
    script.src = KAKAO_POSTCODE_SCRIPT_URL
    script.async = true
    script.onload = handleLoad
    script.onerror = handleError

    document.head.appendChild(script)
  })

  return window.__kakaoPostcodeLoader__
}

export function DesignerApplicationDialog({
  open,
  onOpenChange,
}: DesignerApplicationDialogProps) {
  const [form, setForm] = useState<DesignerApplicationForm>(INITIAL_FORM)
  const [submitAttempted, setSubmitAttempted] = useState(false)
  const [addressSearchError, setAddressSearchError] = useState<string | null>(
    null,
  )
  const [isAddressScriptLoading, setIsAddressScriptLoading] = useState(false)

  const mutation = useMutation({
    mutationFn: (payload: DesignerApplicationRequest) =>
      submitDesignerApplication(payload),
  })
  const resetDesignerApplication = mutation.reset

  useEffect(() => {
    if (open) {
      setIsAddressScriptLoading(true)

      void loadKakaoPostcodeScript()
        .then(() => {
          setAddressSearchError(null)
        })
        .catch((caught) => {
          setAddressSearchError(
            caught instanceof Error
              ? caught.message
              : '카카오 주소 검색을 준비하지 못했습니다.',
          )
        })
        .finally(() => {
          setIsAddressScriptLoading(false)
        })

      return
    }

    setForm(INITIAL_FORM)
    setSubmitAttempted(false)
    setAddressSearchError(null)
    setIsAddressScriptLoading(false)
    resetDesignerApplication()
  }, [open, resetDesignerApplication])

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

  function handleSearchAddress() {
    if (mutation.isPending || isAddressScriptLoading) {
      return
    }

    if (!window.kakao?.Postcode) {
      setAddressSearchError('카카오 주소 검색을 준비하지 못했습니다.')
      return
    }

    setAddressSearchError(null)

    new window.kakao.Postcode({
      oncomplete: (data) => {
        const primaryAddress = data.roadAddress || data.jibunAddress
        const zonecode = data.zonecode ? `(${data.zonecode}) ` : ''
        const buildingName = data.buildingName ? ` ${data.buildingName}` : ''

        handleChange(
          'salonAddress',
          `${zonecode}${primaryAddress}${buildingName}`.trim(),
        )
      },
    }).open()
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
            <Button
              variant="login"
              size="full"
              onClick={() => onOpenChange(false)}
            >
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
                자격증 번호와 미용실 주소를
                <br />
                입력한 뒤 신청해 주세요.
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
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <MapPin className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-warm-400" />
                    <input
                      id="designer-salon-address"
                      type="text"
                      value={form.salonAddress}
                      readOnly
                      placeholder={
                        isAddressScriptLoading
                          ? '주소 검색을 준비하고 있습니다'
                          : '주소 검색 버튼으로 미용실 주소를 선택해 주세요'
                      }
                      className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface pl-11 pr-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
                      disabled={mutation.isPending || isAddressScriptLoading}
                    />
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-12 shrink-0 rounded-2xl px-4 text-text-dark"
                    onClick={handleSearchAddress}
                    disabled={mutation.isPending || isAddressScriptLoading}
                  >
                    <Search className="h-4 w-4" />
                    주소 검색
                  </Button>
                </div>
                <FieldError>
                  {salonAddressError ?? addressSearchError}
                </FieldError>
              </Field>
            </FieldGroup>

            {mutation.isError ? (
              <p className="text-sm text-error" role="alert">
                디자이너 신청 중 오류가 발생했습니다.
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
