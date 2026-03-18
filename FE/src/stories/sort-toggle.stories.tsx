import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { SortToggle } from '@/components/ui/sort-toggle'

const SORT_OPTIONS = [
  { value: 'popular', label: '인기순' },
  { value: 'latest', label: '최신순' },
] as const

type SortValue = (typeof SORT_OPTIONS)[number]['value']

const meta = {
  title: 'UI/SortToggle',
  component: SortToggle,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof SortToggle>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => {
    const [value, setValue] = useState<SortValue>('popular')
    return (
      <SortToggle
        options={SORT_OPTIONS}
        value={value}
        onChange={setValue}
      />
    )
  },
}

export const Latest: Story = {
  render: () => {
    const [value, setValue] = useState<SortValue>('latest')
    return (
      <SortToggle
        options={SORT_OPTIONS}
        value={value}
        onChange={setValue}
      />
    )
  },
}
