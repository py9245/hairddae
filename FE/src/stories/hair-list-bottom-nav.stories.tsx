import type { Meta, StoryObj } from '@storybook/react-vite'
import React from 'react'

import { HairListBottomNav } from '@/components/hair-list-bottom-nav'

const meta = {
  title: 'Navigation/HairListBottomNav',
  component: HairListBottomNav,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story: () => React.ReactNode) => (
      <div className="relative h-[160px] w-[390px] overflow-hidden bg-bg-primary">
        <Story />
      </div>
    ),
  ],
  tags: ['autodocs'],
  args: {
    interactive: false,
  },
} satisfies Meta<typeof HairListBottomNav>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
