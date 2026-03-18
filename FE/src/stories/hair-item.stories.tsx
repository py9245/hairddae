import { useEffect, useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'
import { HairSelector } from '@/components/Camera/hair-selector'
import { HAIR_ITEMS } from '@/lib/Camera/HairItem'
import type { HairItem } from '@/lib/Camera/HairItem'

type HairSelectorStoryProps = {
  items: HairItem[]
  initialSelectedId: number
  loading?: boolean
  onCapture?: () => void
}

function HairSelectorStory({
  items,
  initialSelectedId,
  loading = false,
  onCapture,
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
      onCapture={onCapture}
    />
  )
}

const meta = {
  title: 'UI/Selector/HairSelector',
  component: HairSelectorStory,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
카메라 화면 하단에 위치하는 헤어 선택 셀렉터입니다.

- 좌우 스와이프 또는 버튼 선택으로 헤어 스타일을 탐색할 수 있습니다.
- 선택된 아이템은 중앙에 강조되어 표시됩니다.
- 로딩 중에는 스켈레톤 상태를 표시합니다.
- 캡처 액션과 연결될 수 있도록 onCapture 콜백을 받을 수 있습니다.
        `,
      },
    },
  },
  args: {
    items: HAIR_ITEMS,
    initialSelectedId: 1,
    loading: false,
    onCapture: fn(),
  },
  argTypes: {
    items: {
      control: 'object',
      description: '하단 Controls에서 HairItem 배열을 직접 수정합니다.',
      table: {
        type: { summary: 'HairItem[]' },
      },
    },
    initialSelectedId: {
      control: { type: 'number' },
      description: '초기 선택 hair id입니다.',
      table: {
        type: { summary: 'number' },
      },
    },
    loading: {
      control: { type: 'boolean' },
      description: '헤어 버튼 대신 스켈레톤을 먼저 표시합니다.',
      table: {
        type: { summary: 'boolean' },
        defaultValue: { summary: 'false' },
      },
    },
    onCapture: {
      description: '캡처 버튼 클릭 시 실행되는 콜백 함수입니다.',
      action: 'captured',
      table: {
        type: { summary: '() => void' },
      },
    },
  },
} satisfies Meta<typeof HairSelectorStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  parameters: {
    docs: {
      description: {
        story: '기본 헤어 선택 상태입니다.',
      },
    },
  },
}

export const Skeleton: Story = {
  args: {
    items: [],
    loading: true,
    initialSelectedId: 0,
  },
  parameters: {
    docs: {
      description: {
        story: '헤어 목록을 불러오기 전 스켈레톤 상태입니다.',
      },
    },
  },
}