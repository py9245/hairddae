import type { Meta, StoryObj } from '@storybook/react-vite'
import { LoadingPage } from '@/components/loading-page'

const meta = {
  title: 'Feedback/LoadingPage',
  component: LoadingPage,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof LoadingPage>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
