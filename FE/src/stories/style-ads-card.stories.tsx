import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'
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
  hairName: '레이어컷',
  hairSlug: '분위기 시작의 허리까지 긴 생머리',
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
      onApply={fn()}
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

export const WithApplyAction: Story = {
  args: {
    ...baseArgs,
    liked: false,
    onApply: fn(),
  },
  parameters: {
    docs: {
      description: {
        story:
          '카드 하단에 `적용하기` 버튼이 고정 노출됩니다.',
      },
    },
  },
}

export const Skeleton: Story = {
  args: { ...baseArgs },
  render: () => <StyleAdsCardSkeleton />,
}
