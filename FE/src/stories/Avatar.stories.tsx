import type { Meta, StoryObj } from '@storybook/react-vite'
import { Avatar } from '@/components/ui/avatar'

const meta = {
  title: 'UI/Avatar',
  component: Avatar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: { type: 'select' },
      options: [1, 2, 3, 4, 5],
    },
    loading: {
      control: 'boolean',
    },
  },
} satisfies Meta<typeof Avatar>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    variant: 1,
    loading: false,
  },
}

export const AllVariants: Story = {
  render: () => (
    <div className="flex items-center gap-4">
      <Avatar variant={1} />
      <Avatar variant={2} />
      <Avatar variant={3} />
      <Avatar variant={4} />
      <Avatar variant={5} />
    </div>
  ),
}

export const Skeleton: Story = {
  args: {
    loading: true,
  },
}
