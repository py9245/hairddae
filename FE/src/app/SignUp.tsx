import { Link, useRouter } from '@tanstack/react-router'
import { Eye, EyeClosed } from 'lucide-react'
import { useState } from 'react'
import { AgreementCheckbox } from '@/components/Auth/AgreementCheckbox'
import { useSignUpForm } from '@/hooks/Auth/SignUp/useSignUpForm'
import { useSignUpMutation } from '@/hooks/Auth/SignUp/useSignUpMutation'
import { GenderSelect, type Gender } from '@/components/Auth/GenderSelect'

export default function SignUp() {
  const [showPassword, setShowPassword] = useState(false)
  const [showPasswordConfirm, setShowPasswordConfirm] = useState(false)

  const router = useRouter()
  const signUpMutation = useSignUpMutation()

  const {
    values,
    errors,
    isFormValid,
    handleChange,
    handleBlur,
    handleAgeChange,
    handleSubmit,
  } = useSignUpForm()

  return (
    <div className="rounded-3xl bg-white px-9 py-8 shadow-sm">
      <div className="mx-auto w-full max-w-md">
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
                age: formValues.age ? Number(formValues.age) : undefined,
                gender: formValues.gender || undefined,
              })

              await router.navigate({ to: '/auth/login' })
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
              className={`h-12 w-full rounded-2xl border px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                errors.userId
                  ? 'border-red-400 focus:border-red-400'
                  : 'border-gray-200 focus:border-primary-200'
              }`}
            />
            {errors.userId && (
              <p className="mt-2 text-sm text-red-500">{errors.userId}</p>
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
                className={`h-12 w-full rounded-2xl border px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                  errors.password
                    ? 'border-red-400 focus:border-red-400'
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
              <p className="mt-2 text-sm text-red-500">{errors.password}</p>
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
                className={`h-12 w-full rounded-2xl border px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                  errors.passwordConfirm
                    ? 'border-red-400 focus:border-red-400'
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
              <p className="mt-2 text-sm text-red-500">
                {errors.passwordConfirm}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="age"
                className="mb-2 block text-base font-semibold text-slate-700"
              >
                나이{' '}
                <span className="text-sm font-medium text-gray-400">
                  (선택)
                </span>
              </label>
              <input
                id="age"
                type="text"
                inputMode="numeric"
                value={values.age}
                onChange={(e) => handleAgeChange(e.target.value)}
                onBlur={() => handleBlur('age')}
                maxLength={3}
                placeholder="ex. 25"
                className={`h-12 w-full rounded-2xl border px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
                  errors.age
                    ? 'border-red-400 focus:border-red-400'
                    : 'border-gray-200 focus:border-primary-200'
                }`}
              />
              {errors.age && (
                <p className="mt-2 text-sm text-red-500">{errors.age}</p>
              )}
            </div>

        <div>
          <label
            htmlFor="gender"
            className="mb-2 block text-base font-semibold text-slate-700"
          >
            성별{' '}
            <span className="text-sm font-medium text-gray-400">(선택)</span>
          </label>

          <GenderSelect
            value={values.gender as Gender}
            onChange={(value) => handleChange('gender', value)}
            onBlur={() => handleBlur('gender')}
            error={Boolean(errors.gender)}
          />
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
            <p className="text-center text-sm text-red-500">{errors.agreed}</p>
          )}

          {signUpMutation.isError && (
            <p className="text-center text-sm text-red-500">
              {signUpMutation.error instanceof Error
                ? signUpMutation.error.message
                : '회원가입 처리 중 오류가 발생했습니다.'}
            </p>
          )}

          <button
            type="submit"
            disabled={!isFormValid || signUpMutation.isPending}
            className={`mt-4 h-12 w-full rounded-2xl text-lg font-bold text-white transition ${
              !isFormValid || signUpMutation.isPending
                ? 'bg-primary-100 cursor-not-allowed'
                : 'bg-primary-300 hover:bg-primary-200 cursor-pointer'
            }`}
          >
            {signUpMutation.isPending ? '가입 중...' : '가입하기'}
          </button>
        </form>

        <p className="mt-10 text-center text-sm font-medium text-slate-500">
          이미 계정이 있으신가요?{' '}
          <Link to="/auth/login" className="text-sm font-bold text-primary-300">
            로그인
          </Link>
        </p>
      </div>
    </div>
  )
}
