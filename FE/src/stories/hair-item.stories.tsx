import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { HairSelector } from '@/components/Camera/hair-selector'
import { HAIR_ITEMS } from '../lib/Camera/HairItem'

function HairSelectorStory() {
  const [selectedId, setSelectedId] = useState(1)

  return (
      <HairSelector
        items={HAIR_ITEMS}
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
} satisfies Meta<typeof HairSelectorStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
