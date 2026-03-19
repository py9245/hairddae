import type { Meta, StoryObj } from '@storybook/react-vite'

import { LoginButton } from '@/components/Auth/login-button'

const meta = {
  title: 'UI/Button/LoginButton',
  component: LoginButton,
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
    isPending: false,
  },
  argTypes: {
    disabled: { control: 'boolean' },
    isPending: { control: 'boolean' },
  },
} satisfies Meta<typeof LoginButton>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Disabled: Story = {
  args: { disabled: true },
}

export const Pending: Story = {
  args: { isPending: true },
}
