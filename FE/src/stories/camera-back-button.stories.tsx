import type { Meta, StoryObj } from '@storybook/react-vite'
import { X } from 'lucide-react'
import { fn } from 'storybook/test'

function TopButtonsDemo({
  onBack,
}: {
  onBack?: () => void
}) {
  return (
    <div className="bg-black p-4">
      <button
        type="button"
        aria-label="메인 페이지로 이동"
        title="메인 페이지로 이동"
        onClick={onBack}
        className="flex h-11 w-11 items-center justify-center text-white/85 transition hover:text-white"
      >
        <X className="h-10 w-10" />
      </button>
    </div>
  )
}

const meta = {
  title: 'UI/Button/CameraBackButton',
  component: TopButtonsDemo,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: '카메라 화면에서 메인 페이지로 돌아가는 뒤로가기 버튼입니다.',
      },
    },
  },
  args: {
    onBack: fn(),
  },
} satisfies Meta<typeof TopButtonsDemo>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: '메인 페이지 이동 버튼',
}