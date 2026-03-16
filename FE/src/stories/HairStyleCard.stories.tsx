import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { HairStyleCard } from '@/components/ui/hair-style-card'

const meta = {
  title: 'UI/HairStyleCard',
  component: HairStyleCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  decorators: [
    (Story) => (
      <div className="w-[170px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof HairStyleCard>

export default meta

type Story = StoryObj<typeof meta>

const baseArgs = {
  imageSrc: '/hiar-style/style-01-image.png',
  imageAlt: '레이어드 컷 헤어 스타일 예시',
  title: '우주 킹왕짱\n멋있는 헤어',
  subtitle: '레이어드 컷',
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

export const Priority: Story = {
  args: {
    ...baseArgs,
    priority: true,
  },
}

function InteractiveHairStyleCard() {
  const [liked, setLiked] = useState(false)

  return (
    <HairStyleCard
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
  render: () => <InteractiveHairStyleCard />,
}
