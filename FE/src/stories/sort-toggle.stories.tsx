import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { SortToggle } from '@/components/ui/sort-toggle'
import { SortToggleSkeleton } from '@/components/ui/sort-toggle-skeleton'

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
  args: {
    options: SORT_OPTIONS,
    value: 'popular',
    onChange: () => {},
  },
} satisfies Meta<typeof SortToggle>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    value: 'popular',
  },
  render: (args) => {
    const [value, setValue] = useState<SortValue>(args.value as SortValue)

    return (
      <SortToggle
        {...args}
        options={SORT_OPTIONS}
        value={value}
        onChange={setValue}
      />
    )
  },
}

export const Latest: Story = {
  args: {
    value: 'latest',
  },
  render: (args) => {
    const [value, setValue] = useState<SortValue>(args.value as SortValue)

    return (
      <SortToggle
        {...args}
        options={SORT_OPTIONS}
        value={value}
        onChange={setValue}
      />
    )
  },
}

export const Skeleton: StoryObj = {
  render: () => <SortToggleSkeleton />,
}