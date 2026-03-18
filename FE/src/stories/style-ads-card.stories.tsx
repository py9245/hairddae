import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { StyleAdsCard, StyleAdsCardSkeleton } from '@/components/ui/style-ads-card'

const meta = {
  title: 'UI/Card/StyleAdsCard',
  component: StyleAdsCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[360px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof StyleAdsCard>

export default meta

type Story = StoryObj<typeof meta>

const baseArgs = {
  hairImgpath: '/hiar-style/style-02-image.png',
  hairName: '레이어드컷',
  hairSlug: '봄의 시작을 알리는 여신머리',
}

export const Default: Story = {
  args: {
    ...baseArgs,
    liked: false,
  },
}

export const Liked: Story = {
  args: {
    ...baseArgs,
    liked: true,
  },
}

function InteractiveStyleAdsCard() {
  const [liked, setLiked] = useState(false)

  return (
    <StyleAdsCard
      {...baseArgs}
      liked={liked}
      onLikeToggle={() => setLiked((prev) => !prev)}
    />
  )
}

export const Interactive: Story = {
  args: {
    ...baseArgs,
    liked: false,
  },
  render: () => <InteractiveStyleAdsCard />,
}

export const Skeleton: Story = {
  args: { ...baseArgs },
  render: () => <StyleAdsCardSkeleton />,
}

