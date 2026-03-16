import { Link, useRouter } from '@tanstack/react-router'
import { Eye, EyeClosed } from 'lucide-react'
import { useState } from 'react'
import { useLoginMutation } from '@/hooks/Auth/Login/useLoginMutation'
import { auth } from '@/lib/auth'

type LoginForm = {
  userID: string
  password: string
}

export default function Login() {
  const [showPassword, setShowPassword] = useState(false)
  const [input, setInput] = useState<LoginForm>({ userID: '', password: '' })

  const router = useRouter()
  const loginMutation = useLoginMutation()

  const isFormValid = input.userID.trim() !== '' && input.password.trim() !== ''
  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const { id, value } = e.target
    setInput((prev) => ({ ...prev, [id]: value }))
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!isFormValid) return

    try {
      await loginMutation.mutateAsync({
        userID: input.userID,
        password: input.password,
      })
      auth.login()
      await router.navigate({ to: '/main' })
    } catch (error) {
      console.error(error)
    }
  }

  return (
    <div className="rounded-3xl bg-white px-9 py-8 shadow-sm">
      <div className="mx-auto w-full max-w-md">
        <h1 className="mt-4 text-center text-3xl font-extrabold tracking-tight text-primary-300">
          로그인
        </h1>

        <form className="mt-10 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label
              htmlFor="userID"
              className="mb-2 block text-base font-semibold text-slate-700"
            >
              아이디
            </label>
            <input
              id="userID"
              type="text"
              value={input.userID}
              onChange={handleChange}
              placeholder="아이디를 입력하세요"
              className="h-12 w-full rounded-2xl border border-gray-200 px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
            />
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
                value={input.password}
                onChange={handleChange}
                placeholder="비밀번호를 입력하세요"
                className="h-12 w-full rounded-2xl border border-gray-200 px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
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
          </div>

          {loginMutation.isError && (
            <p className="text-center text-sm text-red-500">
              {loginMutation.error.message}
            </p>
          )}

          <button
            type="submit"
            disabled={!isFormValid || loginMutation.isPending}
            className={`mt-4 h-12 w-full rounded-2xl text-lg font-bold text-white transition ${
              !isFormValid || loginMutation.isPending
                ? 'cursor-not-allowed bg-primary-100'
                : 'cursor-pointer bg-primary-300 hover:bg-primary-200'
            }`}
          >
            {loginMutation.isPending ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <p className="mt-10 text-center text-sm font-medium text-slate-500">
          아직 계정이 없으신가요?{' '}
          <Link
            to="/auth/signup"
            className="text-sm font-bold text-primary-300"
          >
            회원가입
          </Link>
        </p>
      </div>
    </div>
  )
}
