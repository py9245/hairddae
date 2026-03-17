import { useEffect, useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { HairSelector } from '@/components/Camera/hair-selector'
import { HAIR_ITEMS } from '@/lib/Camera/HairItem'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorStoryProps = {
  items: HairItem[]
  initialSelectedId: number
  loading?: boolean
}

function HairSelectorStory({
  items,
  initialSelectedId,
  loading = false,
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
      loading={loading}
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
    loading: false,
  },
  argTypes: {
    items: {
      control: 'object',
      description: '?섎떒 Controls?먯꽌 HairItem 諛곗뿴??吏곸젒 ?섏젙',
    },
    initialSelectedId: {
      control: { type: 'number' },
      description: '珥덇린 ?좏깮 hair id',
    },
    loading: {
      control: { type: 'boolean' },
      description: '헤어 버튼 대신 스켈레톤을 먼저 표시',
    },
  },
} satisfies Meta<typeof HairSelectorStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Skeleton: Story = {
  args: {
    items: [],
    loading: true,
    initialSelectedId: 0,
  },
}
