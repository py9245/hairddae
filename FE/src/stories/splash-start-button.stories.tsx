import type { Meta, StoryObj } from '@storybook/react-vite'
import { Button } from '@/components/ui/button'

const meta = {
  title: 'UI/Button/SplashStartButton',
  component: Button,
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
} satisfies Meta<typeof Button>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    children: '헤어 어때 시작하기',
    className:
      'h-14 w-full rounded-[8px] bg-[#ea7589] px-6 py-4 text-base font-medium leading-[1.4] text-[#f2f2f7] hover:bg-[#e1637b]',
  },
}
