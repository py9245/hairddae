import type { Meta, StoryObj } from '@storybook/react-vite'
import { GuideModal } from '@/components/guide-modal'

const meta = {
  title: 'Modal/GuideModal',
  component: GuideModal,
  parameters: {
    layout: 'centered',
  },
  args: {
    open: true,
    onClose: () => {},
    onDismiss: () => {},
    scale: 1,
  },
} satisfies Meta<typeof GuideModal>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
