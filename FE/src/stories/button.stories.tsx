import type { Meta, StoryObj } from '@storybook/react-vite'
import { Download, Settings, X } from 'lucide-react'
import { Button } from '@/components/ui/button'

const meta = {
  title: 'UI/Button',
  component: Button,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: [
        'default',
        'splash',
        'login',
        'logout',
        'camera-back',
        'camera-setting',
        'hair-download',
      ],
    },
    size: {
      control: { type: 'select' },
      options: [
        'default',
        'xs',
        'sm',
        'lg',
        'icon',
        'icon-xs',
        'icon-sm',
        'icon-lg',
        'full',
        'splash',
        'camera-icon',
        'camera-download',
      ],
    },
  },
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    variant: 'default',
    children: '버튼',
  },
}

export const Logout: Story = {
  args: {
    variant: 'logout',
    size: 'full',
    children: '로그아웃',
  },
  decorators: [
    (Story) => (
      <div className="w-80">
        <Story />
      </div>
    ),
  ],
}

export const CameraBack: Story = {
  args: {
    variant: 'camera-back',
    size: 'camera-icon',
    children: <X className="size-12 text-white" />,
    'aria-label': '닫기',
  },
  decorators: [
    (Story) => (
      <div className="bg-black p-4">
        <Story />
      </div>
    ),
  ],
}

export const CameraSetting: Story = {
  args: {
    variant: 'camera-setting',
    size: 'camera-icon',
    children: <Settings className="size-12 text-white" />,
    'aria-label': '설정 열기',
  },
  decorators: [
    (Story) => (
      <div className="bg-black p-4">
        <Story />
      </div>
    ),
  ],
}

export const HairDownload: Story = {
  args: {
    variant: 'hair-download',
    size: 'camera-download',
    children: <Download className="size-12 text-slate-700" />,
    'aria-label': '캡처 다운로드',
  },
  decorators: [
    (Story) => (
      <Story />
    ),
  ],
}
