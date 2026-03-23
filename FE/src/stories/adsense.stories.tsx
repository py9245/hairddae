import type { Meta, StoryObj } from '@storybook/react-vite'
import Adsense from '@/app/adsense'

const meta = {
  title: 'UI/Adsense',
  component: Adsense,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="flex min-h-screen items-start justify-center p-6">
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
    forceVisible: true,
  },
}

export const Skeleton: Story = {
  args: {
    loading: true,
    forceVisible: true,
  },
}
