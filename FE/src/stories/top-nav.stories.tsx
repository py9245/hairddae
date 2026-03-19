import type { Meta, StoryObj } from '@storybook/react-vite'
import { Settings, X } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { TopNav } from '@/components/top-nav'

const meta = {
  title: 'Navigation/TopNav',
  component: TopNav,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <div className="flex items-center justify-center">
        <div className="relative h-20 w-[430px] max-w-full overflow-hidden bg-black">
          <Story />
        </div>
      </div>
    ),
  ],
} satisfies Meta<typeof TopNav>

export default meta

type Story = StoryObj<typeof meta>

export const CameraActions: Story = {
  render: () => (
    <TopNav
      leftAction={
        <Button
          type="button"
          variant="camera-back"
          size="camera-icon"
          aria-label="닫기"
        >
          <X className="size-10 text-white" />
        </Button>
      }
      rightAction={
        <Button
          type="button"
          variant="camera-setting"
          size="camera-icon"
          aria-label="설정 열기"
        >
          <Settings className="size-10 text-white" />
        </Button>
      }
    />
  ),
}
