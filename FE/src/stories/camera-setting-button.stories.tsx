import type { Meta, StoryObj } from '@storybook/react-vite'
import { Settings } from 'lucide-react'
import { fn } from 'storybook/test'

function TopButtonsDemo({
  onOpenSettings,
}: {
  onOpenSettings?: () => void
}) {
  return (
    <div className="bg-black p-4">
      <button
        type="button"
        aria-label="설정 열기"
        title="설정 열기"
        onClick={onOpenSettings}
        className="flex h-11 w-11 items-center justify-center text-white/85 transition hover:text-white"
      >
        <Settings className="h-10 w-10" />
      </button>
    </div>
  )
}

const meta = {
  title: 'UI/Button/CameraSettingButton',
  component: TopButtonsDemo,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: '카메라 화면에서 설정 모달 띄우는 버튼',
      },
    },
  },
  args: {
    onOpenSettings: fn(),
  },
} satisfies Meta<typeof TopButtonsDemo>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: '설정창 띄우는 버튼',
}