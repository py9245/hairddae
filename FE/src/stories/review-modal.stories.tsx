import type { Meta, StoryObj } from '@storybook/react-vite'
import { ReviewModal } from '@/components/review-modal'

const meta = {
  title: 'Modal/ReviewModal',
  component: ReviewModal,
  parameters: {
    layout: 'centered',
  },
  args: {
    open: true,
    onClose: () => {},
  },
} satisfies Meta<typeof ReviewModal>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
