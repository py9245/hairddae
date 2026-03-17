import { useEffect, useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { HairSelector } from '@/components/Camera/hair-selector'
import { HAIR_ITEMS } from '@/lib/Camera/HairItem'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorStoryProps = {
  items: HairItem[]
  initialSelectedId: number
}

function HairSelectorStory({
  items,
  initialSelectedId,
}: HairSelectorStoryProps) {
  const [selectedId, setSelectedId] = useState(initialSelectedId)

  useEffect(() => {
    setSelectedId(initialSelectedId)
  }, [initialSelectedId])

  useEffect(() => {
    if (!items.some((item) => item.id === selectedId) && items.length > 0) {
      setSelectedId(items[0].id)
    }
  }, [items, selectedId])

  return (
    <HairSelector
      items={items}
      selectedId={selectedId}
      onSelect={setSelectedId}
      onCapture={() => {
        console.log('capture:', selectedId)
      }}
    />
  )
}

const meta = {
  title: 'UI/Selector/HairSelector',
  component: HairSelectorStory,
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    items: HAIR_ITEMS,
    initialSelectedId: 1,
  },
  argTypes: {
    items: {
      control: 'object',
      description: '하단 Controls에서 HairItem 배열을 직접 수정',
    },
    initialSelectedId: {
      control: { type: 'number' },
      description: '초기 선택 hair id',
    },
  },
} satisfies Meta<typeof HairSelectorStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}