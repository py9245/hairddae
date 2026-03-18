import type { Meta, StoryObj } from '@storybook/react-vite'
import Adsense from '@/app/Adsense'

const meta = {
  title: 'UI/Adsense',
  component: Adsense,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="flex min-h-screen items-start justify-center bg-gray-100 p-6">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Adsense>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    loading: false,
  },
}

export const Skeleton: Story = {
  args: {
    loading: true,
  },
}