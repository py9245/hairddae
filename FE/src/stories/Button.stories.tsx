import type { Meta, StoryObj } from '@storybook/react-vite'
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
        'destructive',
        'outline',
        'secondary',
        'ghost',
        'link',
        'logout',
      ],
    },
    size: {
      control: { type: 'select' },
      options: ['default', 'xs', 'sm', 'lg', 'icon', 'full'],
    },
  },
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
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
