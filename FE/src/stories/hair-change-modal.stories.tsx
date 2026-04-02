import type { Meta, StoryObj } from '@storybook/react-vite'
import { ApplyStyleModal } from '@/components/Camera/modal'

const meta = {
  title: 'Modal/HairChangeModal',
  component: ApplyStyleModal,
  parameters: {
    layout: 'centered',
  },
  args: {
    open: true,
    completed: false,
    content: undefined,
  },
} satisfies Meta<typeof ApplyStyleModal>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const CustomContent: Story = {
  args: {
    content: {
      title: '선택하신 스타일을 적용 중이에요',
      tips: [
        '얼굴 윤곽을 살려보세요',
        '앞머리는 너무 짧지 않게',
        '볼륨은 자연스럽게 분산',
      ],
    },
  },
}

export const Completed: Story = {
  args: {
    completed: true,
  },
}