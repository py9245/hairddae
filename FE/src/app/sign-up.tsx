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
      <main className="app-frame-page flex flex-col items-center justify-center bg-bg-primary px-6 mb-20">
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
    <main className="app-frame-page flex flex-col items-center justify-center bg-bg-primary px-6 py-10">
      <div className="w-full max-w-md">
        <h1 className="mt-4 text-center text-3xl font-extrabold tracking-tight text-primary-300">
          회원가입
        </h1>

        <form
          className="mt-10 space-y-5"
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
            <label
              htmlFor="userId"
              className="mb-2 block text-base font-semibold text-slate-700"
            >
              아이디
            </label>
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
            {errors.userId && (
              <p className="mt-2 text-sm text-error">{errors.userId}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="mb-2 block text-base font-semibold text-slate-700"
            >
              비밀번호
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={values.password}
                maxLength={16}
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
            {errors.password && (
              <p className="mt-2 text-sm text-error">{errors.password}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="passwordConfirm"
              className="mb-2 block text-base font-semibold text-slate-700"
            >
              비밀번호 확인
            </label>
            <div className="relative">
              <input
                id="passwordConfirm"
                type={showPasswordConfirm ? 'text' : 'password'}
                maxLength={16}
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
            {errors.passwordConfirm && (
              <p className="mt-2 text-sm text-error">
                {errors.passwordConfirm}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="birthDate"
                className="mb-2 block text-base font-semibold text-slate-700"
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
                <p className="mt-2 text-sm text-primary-300">
                  {errors.birthDate}
                </p>
              )}
            </div>

            <div className="space-y-2">
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

          <AgreementCheckbox
            checked={values.agreed}
            onChange={(checked) => handleChange('agreed', checked)}
            onBlur={() => handleBlur('agreed')}
            label="이용약관 및 개인정보수집에 동의합니다."
            requiredText="[필수]"
          />
          {errors.agreed && (
            <p className="text-center text-sm text-error">{errors.agreed}</p>
          )}

          {signUpMutation.isError && (
            <p className="text-center text-sm text-error">
              {signUpMutation.error instanceof Error
                ? signUpMutation.error.message
                : '회원가입 처리 중 오류가 발생했습니다.'}
            </p>
          )}

          <SignUpButton
            className="mt-4"
            disabled={!isFormValid}
            isPending={signUpMutation.isPending}
          />
        </form>

        <p className="mt-10 text-center text-sm font-medium text-slate-500">
          이미 계정이 있으신가요?{' '}
          <Link to="/auth/login" className="text-sm font-bold text-primary-300">
            로그인
          </Link>
        </p>
      </div>
    </main>
  )
}
