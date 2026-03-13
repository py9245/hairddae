import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

type LoginButtonPreviewProps = {
  isValid: boolean
  initialPending?: boolean
  pendingOnClick?: boolean
}

function LoginButtonPreview({
  isValid,
  initialPending = false,
  pendingOnClick = true,
}: LoginButtonPreviewProps) {
  const [isPending, setIsPending] = useState(initialPending)

  const disabled = !isValid || isPending
  const className = `mt-4 h-12 w-80 rounded-2xl text-lg font-bold text-white transition ${
    disabled
      ? 'cursor-not-allowed bg-rose-200'
      : 'cursor-pointer bg-rose-400 hover:bg-rose-500'
  }`

  return (
    <button
      type="button"
      disabled={disabled}
      className={className}
      aria-busy={isPending || undefined}
      onClick={() => {
        if (!disabled && pendingOnClick) {
          setIsPending(true)
          setTimeout(() => setIsPending(false), 1200)
        }
      }}
    >
      {isPending ? '로그인 중...' : '로그인'}
    </button>
  )
}

const meta = {
  title: 'Auth/LoginButton',
  component: LoginButtonPreview,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  args: {
    isValid: true,
    initialPending: false,
    pendingOnClick: true,
  },
  argTypes: {
    isValid: { control: 'boolean' },
    initialPending: { control: 'boolean' },
    pendingOnClick: { control: 'boolean' },
  },
} satisfies Meta<typeof LoginButtonPreview>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
export const Disabled: Story = { args: { isValid: false } }
export const Pending: Story = {
  args: { initialPending: true, pendingOnClick: false },
}

