import type { Meta, StoryObj } from '@storybook/react-vite'
import { useMemo, useState } from 'react'
import { Eye, EyeClosed } from 'lucide-react'
import { validateField, type FormValues } from '@/lib/Auth/SignUp/signupValidation'
import { userEvent, within } from 'storybook/test'

type LabelKind = '라벨을 입력하세요' | '아이디' | '비밀번호' | '비밀번호 확인'

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
    birthDate: '2026-03-17',
    gender: null,
    agreed: true,
  }
  const key =
    label === '아이디'
      ? 'userId'
      : label === '비밀번호'
        ? 'password'
        : label === '비밀번호 확인'
          ? 'passwordConfirm'
          : 'birthDate'
  return validateField(key, form) ?? null
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
              hasError ? 'border-red-400 focus:border-red-400' : 'border-gray-200 focus:border-primary-200'
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
  title: 'UI/Input',
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
      description: "라벨이 '비밀번호 확인'일 때 원래 비밀번호를 넣어주세요.",
    },
  },
} satisfies Meta<typeof InputPreview>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: '라벨을 입력하세요', placeholder: '플레이스홀더를 입력하세요' },
}

export const Password: Story = {
  args: { label: '비밀번호', placeholder: '비밀번호를 입력하세요' },
}

export const PasswordConfirm: Story = {
  args: { label: '비밀번호 확인', placeholder: '비밀번호를 다시 입력하세요', confirmTarget: 'Password1!' },
}

export const UserIdError: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByRole('textbox')
    await userEvent.type(input, 'abc!')
    await userEvent.tab()
  },
}

export const PasswordError: Story = {
  args: { label: '비밀번호' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText('비밀번호') 
    await userEvent.type(input, 'password')
    await userEvent.tab()
  },
}

export const PasswordConfirmError: Story = {
  args: { label: '비밀번호 확인', confirmTarget: 'Password1!' },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText('비밀번호 확인') 
    await userEvent.type(input, 'wrong')
    await userEvent.tab()
  },
}

