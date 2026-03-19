import type { Meta, StoryObj } from '@storybook/react-vite'
import { Settings, X } from 'lucide-react'

import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'

const meta = {
  title: 'Navigation/Header',
  component: Header,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
  },
} satisfies Meta<typeof Header>

export default meta

type Story = StoryObj<typeof meta>

const PageWrapper = ({ children }: { children: React.ReactNode }) => (
  <div className="flex items-center justify-center">
    <div className="w-[430px] max-w-full bg-bg-primary">{children}</div>
  </div>
)

export const MainHeader: Story = {
  render: () => (
    <PageWrapper>
      <Header label="헤어때" labelClassName="text-primary-200" />
    </PageWrapper>
  ),
}

export const HairListHeader: Story = {
  render: () => (
    <PageWrapper>
      <Header label="단발컷" labelClassName="text-neutral-700"/>
    </PageWrapper>
  ),
}

export const MyPageHeader: Story = {
  render: () => (
    <PageWrapper>
      <Header label="내정보" labelClassName="text-neutral-700"/>
    </PageWrapper>
  ),
}

export const CameraActions: Story = {
  decorators: [
    (Story) => (
      <div className="flex items-center justify-center">
        <div className="relative h-20 w-[430px] max-w-full overflow-hidden bg-black">
          <Story />
        </div>
      </div>
    ),
  ],
  render: () => (
    <Header
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

