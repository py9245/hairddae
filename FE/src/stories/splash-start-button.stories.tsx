import type { Meta, StoryObj } from '@storybook/react-vite'

import { SplashStartButton } from '@/components/splash-start-button'

const meta = {
  title: 'UI/Button/SplashStartButton',
  component: SplashStartButton,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[340px]">
        <Story />
      </div>
    ),
  ],
  args: {
    children: '헤어 어때 시작하기',
  },
} satisfies Meta<typeof SplashStartButton>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
