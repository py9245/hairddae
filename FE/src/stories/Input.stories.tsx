import type { Meta, StoryObj } from '@storybook/react-vite'
import { useMemo, useState } from 'react'
import { Eye, EyeClosed } from 'lucide-react'
import { validateField, type FormValues } from '@/lib/Auth/SignUp/signupValidation'

type LabelKind = '아이디' | '비밀번호' | '비밀번호 확인' | '나이'

type InputPreviewProps = {
  label: LabelKind
  placeholder?: string
  confirmTarget?: string
}

function validateValue(
  label: LabelKind,
  value: string,
  confirmTarget?: string,
): string | null {
  const v = value.trim()
  const form: FormValues = {
    userId: label === '아이디' ? v : '',
    password:
      label === '비밀번호'
        ? v
        : label === '비밀번호 확인'
          ? confirmTarget ?? ''
          : '',
    passwordConfirm: label === '비밀번호 확인' ? v : '',
    age: label === '나이' ? v : '',
    gender: '',
    agreed: true,
  }

  const key =
    label === '아이디'
      ? 'userId'
      : label === '비밀번호'
        ? 'password'
        : label === '비밀번호 확인'
          ? 'passwordConfirm'
          : 'age'

  return validateField(key, form) ?? null
}

function InputPreview({ label, placeholder, confirmTarget }: InputPreviewProps) {
  const [value, setValue] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [touched, setTouched] = useState(false)

  const isPassword = label === '비밀번호' || label === '비밀번호 확인'
  const isAge = label === '나이'

  const derivedPlaceholder =
    placeholder ??
    (label === '비밀번호'
      ? '비밀번호를 입력하세요'
      : label === '비밀번호 확인'
        ? '비밀번호를 다시 입력하세요'
        : label === '나이'
          ? 'ex. 25'
          : '아이디를 입력하세요')

  const error = useMemo(
    () => validateValue(label, value, confirmTarget),
    [label, value, confirmTarget],
  )

  const hasError = touched && Boolean(error)
  const ariaToggle = label === '비밀번호 확인' ? '비밀번호 확인' : '비밀번호'

  return (
    <div className="w-[320px]">
      <label
        htmlFor="field"
        className="mb-2 block text-base font-semibold text-slate-700"
      >
        {label}
      </label>

      <div className="relative">
        <input
          id="field"
          type={isPassword && !showPassword ? 'password' : 'text'}
          value={value}
          onChange={(e) =>
            setValue(isAge ? e.target.value.replace(/\D/g, '') : e.target.value)
          }
          onBlur={() => setTouched(true)}
          placeholder={derivedPlaceholder}
          aria-invalid={hasError || undefined}
          aria-describedby={hasError ? 'field-error' : undefined}
          inputMode={isAge ? 'numeric' : undefined}
          maxLength={isAge ? 3 : undefined}
          className={`h-12 w-full rounded-2xl border px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
            hasError
              ? 'border-red-400 focus:border-red-400'
              : 'border-gray-200 focus:border-primary-200'
          }`}
        />

        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
            aria-label={showPassword ? `${ariaToggle} 숨기기` : `${ariaToggle} 보기`}
          >
            {showPassword ? (
              <Eye className="h-5 w-5" />
            ) : (
              <EyeClosed className="h-5 w-5" />
            )}
          </button>
        )}
      </div>

      {hasError && (
        <p id="field-error" className="mt-2 text-sm text-red-500">
          {error}
        </p>
      )}
    </div>
  )
}

const meta = {
  title: 'UI/Input',
  component: InputPreview,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    confirmTarget: {
      control: 'text',
      if: { arg: 'label', eq: '비밀번호 확인' },
      description: "라벨이 '비밀번호 확인'일 때 원 비밀번호를 넣어주세요.",
    },
  },
} satisfies Meta<typeof InputPreview>
export default meta

type Story = StoryObj<typeof meta>

export const UserId: Story = {
  args: {
    label: '아이디',
  },
}

export const Password: Story = {
  args: {
    label: '비밀번호',
  },
}

export const PasswordConfirm: Story = {
  args: {
    label: '비밀번호 확인',
    confirmTarget: 'test1234!',
  },
}

export const Age: Story = {
  args: {
    label: '나이',
  },
}