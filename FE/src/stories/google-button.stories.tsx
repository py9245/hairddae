import type { Meta, StoryObj } from '@storybook/react-vite'
import { GoogleButton } from '@/components/google-button'

const meta = {
  title: 'UI/Button/GoogleButton',
  component: GoogleButton,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[340px]">
        <Story />
      </div>
    ),
  ],
  args: {
    disabled: false,
    label: 'Continue with Google',
  },
  argTypes: {
    disabled: { control: 'boolean' },
    label: { control: 'text' },
  },
} satisfies Meta<typeof GoogleButton>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Disabled: Story = {
  args: { disabled: true },
}
