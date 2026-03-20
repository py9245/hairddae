import type { Meta, StoryObj } from '@storybook/react-vite'
import { ProfileCard, ProfileCardSkeleton } from '@/components/profile-card'

const mockProfile = {
  nickname: 'mijin.develop',
  age: 18,
  gender: 'F',
  avatarVariant: 1 as const,
}

const meta = {
  title: 'UI/Card/ProfileCard',
  component: ProfileCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[357px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProfileCard>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    profile: mockProfile,
    onLogout: () => alert('로그아웃'),
  },
}

export const Skeleton: Story = {
  args: {
    profile: mockProfile,
    onLogout: () => {},
  },
  render: () => <ProfileCardSkeleton />,
}
