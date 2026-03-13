import type { Meta, StoryObj } from '@storybook/react-vite'
import { useMemo, useState } from 'react'
import { Eye, EyeClosed } from 'lucide-react'

type LabelKind = '아이디' | '비밀번호' | '비밀번호 확인'

type InputPreviewProps = {
  label: LabelKind
  placeholder?: string
  // 비밀번호 확인용: 원래 비밀번호 값(선택). 제공되면 불일치 시 경고 표시
  confirmTarget?: string
}

function validateValue(
  label: LabelKind,
  value: string,
  confirmTarget?: string,
): string | null {
  const v = value.trim()

  if (label === '아이디') {
    if (v.length === 0) return '아이디를 입력해 주세요.'
    if (v.length < 6) return '아이디는 6자 이상이어야 해요.'
    if (v.length > 20) return '아이디는 20자 이하로 입력해 주세요.'
    if (!/^[A-Za-z0-9]+$/.test(v))
      return '아이디는 영문/숫자만 사용할 수 있어요.'
    return null
  }

  if (label === '비밀번호') {
    if (v.length === 0) return '비밀번호를 입력해 주세요.'
    if (v.length < 8 || v.length > 16) return '비밀번호는 8~16자여야 해요.'
    if (!/[A-Za-z]/.test(v)) return '비밀번호에는 영문이 최소 1개 필요해요.'
    if (!/[0-9]/.test(v)) return '비밀번호에는 숫자가 최소 1개 필요해요.'
    if (!/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?`~]/.test(v))
      return '비밀번호에는 특수문자가 최소 1개 필요해요.'
    return null
  }

  if (v.length === 0) return '비밀번호 확인을 입력해 주세요.'
  if (typeof confirmTarget === 'string' && v !== confirmTarget)
    return '비밀번호가 일치하지 않습니다.'
  return null
}

function InputPreview({ label, placeholder, confirmTarget }: InputPreviewProps) {
  const [value, setValue] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [touched, setTouched] = useState(false)

  const isPassword = label === '비밀번호' || label === '비밀번호 확인'
  const derivedPlaceholder =
    placeholder ??
    (label === '비밀번호'
      ? '비밀번호를 입력하세요'
      : label === '비밀번호 확인'
        ? '비밀번호를 다시 입력하세요'
        : '아이디를 입력하세요')

  const error = useMemo(
    () => validateValue(label, value, confirmTarget),
    [label, value, confirmTarget],
  )
  const hasError = touched && Boolean(error)

  const ariaToggle = label === '비밀번호 확인' ? '비밀번호 확인' : '비밀번호'

  return (
      <div>
        <label htmlFor="field" className="mb-2 block text-base font-semibold text-slate-700">
          {label}
        </label>
        <div className="relative">
          <input
            id="field"
            type={isPassword && !showPassword ? 'password' : 'text'}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onBlur={() => setTouched(true)}
            placeholder={derivedPlaceholder}
            aria-invalid={hasError || undefined}
            aria-describedby={hasError ? 'field-error' : undefined}
            className={`h-12 w-full rounded-2xl border px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none ${
              hasError ? 'border-red-400 focus:border-red-400' : 'border-gray-200 focus:border-rose-200'
            }`}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
              aria-label={showPassword ? `${ariaToggle} 숨기기` : `${ariaToggle} 보기`}
            >
              {showPassword ? <Eye className="h-5 w-5" /> : <EyeClosed className="h-5 w-5" />}
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
  title: 'Auth/Input',
  component: InputPreview,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  args: {
    label: '아이디' as LabelKind,
  },
  argTypes: {
    label: {
      control: { type: 'select' },
      options: ['아이디', '비밀번호', '비밀번호 확인'],
    },
    placeholder: { control: 'text' },
    confirmTarget: {
      control: 'text',
      description: "라벨이 '비밀번호 확인'일 때 원 비밀번호를 넣어주세요.",
    },
  },
} satisfies Meta<typeof InputPreview>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

