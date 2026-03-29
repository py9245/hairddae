import { Link, useRouter } from '@tanstack/react-router'
import { Eye, EyeClosed } from 'lucide-react'
import { useEffect, useState } from 'react'
import { AgreementCheckbox } from '@/components/Auth/agreement-checkbox'
import { BirthDatePicker } from '@/components/Auth/birth-date-picker'
import { GenderSelect } from '@/components/Auth/gender-select'
import { SignUpButton } from '@/components/Auth/sign-up-button'
import { useSignUpForm } from '@/hooks/Auth/SignUp/useSignUpForm'
import { useSignUpMutation } from '@/hooks/Auth/SignUp/useSignUpMutation'

export default function SignUp() {
  const [showPassword, setShowPassword] = useState(false)
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false)
  const [isSignUpComplete, setIsSignUpComplete] = useState(false)

  const router = useRouter()
  const signUpMutation = useSignUpMutation()

  const {
    values,
    errors,
    isFormValid,
    handleChange,
    handleBlur,
    handleSubmit,
  } = useSignUpForm()
  const userIdLength = values.userId.length
  const passwordLength = values.password.length
  const passwordConfirmLength = values.passwordConfirm.length

  useEffect(() => {
    if (!isSignUpComplete) {
      return
    }

    const timeoutId = window.setTimeout(() => {
      void router.navigate({ to: '/auth/login' })
    }, 3000)

    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [isSignUpComplete, router])

  if (isSignUpComplete) {
    return (
      <main className="app-frame-page h-full flex flex-col items-center justify-center bg-bg-primary px-6">
        <h1 className="h-[54px] whitespace-pre-line px-8 text-center text-[20px] leading-[1.35] font-semibold tracking-[-0.03em] text-text-dar mb-20">
          헤어 어때와 함께 다양한 <br />
          헤어스타일로 꾸며보아요
        </h1>

        <img
          src="/icon/signup.svg"
          alt="회원가입 성공 이미지"
          width={398}
          height={320}
          decoding="async"
          className="h-auto w-full max-w-[398px] object-contain select-none"
        />
      </main>
    )
  }

  return (
    <main className="app-frame-page h-full flex flex-col items-center justify-start overflow-y-auto bg-bg-primary px-6 py-6 md:justify-center md:py-10 [@media_(max-height:820px)]:justify-start [@media_(max-height:820px)]:py-4">
      <div className="w-full max-w-md">
        <h1 className="mt-1 text-center text-3xl font-extrabold tracking-tight text-primary-300 md:mt-4 [@media_(max-height:820px)]:mt-0">
          회원가입
        </h1>

        <form
          className="mt-4 space-y-2.5 md:mt-10 md:space-y-4 [@media_(max-height:820px)]:mt-3 [@media_(max-height:820px)]:space-y-2"
          onSubmit={(e) =>
            handleSubmit(e, async (formValues) => {
              await signUpMutation.mutateAsync({
                userID: formValues.userId,
                password: formValues.password,
                passwordCheck: formValues.passwordConfirm,
                birthDate: formValues.birthDate || undefined,
                gender: formValues.gender ?? undefined,
              })

              setIsSignUpComplete(true)
            })
          }
        >
          <div>
            <div className="mb-1.5 flex items-center">
              <label
                htmlFor="userId"
                className="block text-base font-semibold text-slate-700"
              >
                아이디
              </label>
            </div>
            <input
              id="userId"
              type="text"
              value={values.userId}
              maxLength={20}
              onChange={(e) => handleChange('userId', e.target.value)}
              onBlur={() => handleBlur('userId')}
              placeholder="사용하실 아이디를 입력하세요"
              className={`h-12 w-full rounded-2xl border bg-input-surface px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                errors.userId
                  ? 'border-primary-300 focus:border-error'
                  : 'border-gray-200 focus:border-primary-200'
              }`}
            />
            <div className="mt-1.5 flex items-center justify-between gap-3">
              <p className="min-h-[20px] text-sm text-error">
                {errors.userId ?? ''}
              </p>
              <span className="shrink-0 text-sm text-gray-400">
                {userIdLength}/20자
              </span>
            </div>
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-1.5 block text-base font-semibold text-slate-700"
            >
              비밀번호
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={values.password}
                maxLength={20}
                onChange={(e) => handleChange('password', e.target.value)}
                onBlur={() => handleBlur('password')}
                placeholder="비밀번호 입력"
                className={`h-12 w-full rounded-2xl border bg-input-surface px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                  errors.password
                    ? 'border-error focus:border-error'
                    : 'border-gray-200 focus:border-primary-200'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
                aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'}
              >
                {showPassword ? (
                  <Eye className="h-5 w-5" />
                ) : (
                  <EyeClosed className="h-5 w-5" />
                )}
              </button>
            </div>
            <div className="mt-1.5 flex items-center justify-between gap-3">
              <p className="min-h-[20px] text-sm text-error">
                {errors.password ?? ''}
              </p>
              <span className="shrink-0 text-sm text-gray-400">
                {passwordLength}/20자
              </span>
            </div>
          </div>

          <div>
            <label
              htmlFor="passwordConfirm"
              className="mb-1.5 block text-base font-semibold text-slate-700"
            >
              비밀번호 확인
            </label>
            <div className="relative">
              <input
                id="passwordConfirm"
                type={showPasswordConfirm ? 'text' : 'password'}
                maxLength={20}
                value={values.passwordConfirm}
                onChange={(e) =>
                  handleChange('passwordConfirm', e.target.value)
                }
                onBlur={() => handleBlur('passwordConfirm')}
                placeholder="비밀번호 재입력"
                className={`h-12 w-full rounded-2xl border bg-input-surface px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                  errors.passwordConfirm
                    ? 'border-error focus:border-error'
                    : 'border-gray-200 focus:border-primary-200'
                }`}
              />
              <button
                type="button"
                onClick={() => setShowPasswordConfirm((prev) => !prev)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
                aria-label={
                  showPasswordConfirm
                    ? '비밀번호 확인 숨기기'
                    : '비밀번호 확인 보기'
                }
              >
                {showPasswordConfirm ? (
                  <Eye className="h-5 w-5" />
                ) : (
                  <EyeClosed className="h-5 w-5" />
                )}
              </button>
            </div>
            <div className="mt-1.5 flex items-center justify-between gap-3">
              <p className="min-h-[20px] text-sm text-error">
                {errors.passwordConfirm ?? ''}
              </p>
              <span className="shrink-0 text-sm text-gray-400">
                {passwordConfirmLength}/20자
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-1.5 md:gap-2.5 [@media_(max-height:820px)]:gap-1">
            <div>
              <label
                htmlFor="birthDate"
                className="mb-1.5 block text-base font-semibold text-slate-700"
              >
                생년월일{' '}
                <span className="text-sm font-medium text-gray-400">
                  (선택)
                </span>
              </label>
              <BirthDatePicker
                value={values.birthDate}
                onChange={(v) => handleChange('birthDate', v)}
                onBlur={() => handleBlur('birthDate')}
                hasError={!!errors.birthDate}
              />
              {errors.birthDate && (
                <p className="mt-1.5 text-sm text-primary-300">
                  {errors.birthDate}
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label
                htmlFor="gender"
                className="block text-base font-semibold text-slate-700"
              >
                성별{' '}
                <span className="text-sm font-medium text-gray-400">
                  (선택)
                </span>
              </label>

              <GenderSelect
                id="gender"
                value={values.gender}
                onChange={(value) => handleChange('gender', value)}
                onBlur={() => handleBlur('gender')}
                error={Boolean(errors.gender)}
              />

              {errors.gender ? (
                <p className="text-sm text-error">{errors.gender}</p>
              ) : null}
            </div>
          </div>

          <div className="relative">
            {errors.agreed && (
              <p
                className="absolute left-1/2 top-5 -translate-x-1/2 whitespace-nowrap text- 
            sm text-error"
              >
                {errors.agreed}
              </p>
            )}
            <AgreementCheckbox
              checked={values.agreed}
              onChange={(checked) => handleChange('agreed', checked)}
              onBlur={() => handleBlur('agreed')}
              label="이용약관 및 개인정보수집에 동의합니다."
              requiredText="[필수]"
            />
          </div>

          {signUpMutation.isError && (
            <p className="text-center text-sm text-error">
              {signUpMutation.error instanceof Error
                ? signUpMutation.error.message
                : '회원가입 처리 중 오류가 발생했습니다.'}
            </p>
          )}

          <SignUpButton
            className="mt-3"
            disabled={!isFormValid}
            isPending={signUpMutation.isPending}
          />
        </form>

        <p className="mt-1 text-center text-sm font-medium text-slate-500 md:mt-10 [@media_(max-height:820px)]:mt-2">
          이미 계정이 있으신가요?{' '}
          <Link to="/auth/login" className="text-sm font-bold text-primary-300">
            로그인
          </Link>
        </p>
      </div>
    </main>
  )
}
