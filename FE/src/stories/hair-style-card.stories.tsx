import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'
import { HairStyleCard } from '@/components/ui/hair-style-card'

const meta = {
  title: 'UI/Card/HairStyleCard',
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
  hairId: 1,
  imageSrc: '/hiar-style/style-01-image.png',
  imageAlt: '레이어드 컷 헤어 스타일 예시',
  hairName: '우주 킹왕짱\n멋있는 헤어',
  hookText: '레이어드 컷',
}

export const Default: Story = {
  args: {
    ...baseArgs,
    liked: false,
  },
}


function InteractiveHairStyleCard() {
  const [liked, setLiked] = useState(false)

  return (
    <HairStyleCard
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
  render: () => <InteractiveHairStyleCard />,
}

