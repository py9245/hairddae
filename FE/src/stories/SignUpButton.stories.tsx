import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'

type SignUpButtonPreviewProps = {
  isValid: boolean
  initialPending?: boolean
  pendingOnClick?: boolean
}

function SignUpButtonPreview({
  isValid,
  initialPending = false,
  pendingOnClick = true,
}: SignUpButtonPreviewProps) {
  const [isPending, setIsPending] = useState(initialPending)

  const disabled = !isValid || isPending
  const className = `mt-4 h-12 w-80 rounded-2xl text-lg font-bold text-white transition ${
    disabled
      ? 'bg-rose-200 cursor-not-allowed'
      : 'bg-rose-400 hover:bg-rose-500 cursor-pointer'
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
      {isPending ? '가입 중...' : '가입하기'}
    </button>
  )
}

const meta = {
  title: 'Auth/SignUpButton',
  component: SignUpButtonPreview,
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
} satisfies Meta<typeof SignUpButtonPreview>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
export const Disabled: Story = { args: { isValid: false } }
export const Pending: Story = {
  args: { initialPending: true, pendingOnClick: false },
}

