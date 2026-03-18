import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { GenderSelect, type Gender } from '@/components/Auth/gender-select'

type StoryProps = {
  initialValue: Gender
}

function GenderSelectStory({ initialValue }: StoryProps) {
  const [value, setValue] = useState<Gender>(initialValue)
  return (
        <div className="w-[150px]">
      <GenderSelect value={value} onChange={setValue} />
        </div>
  )
}

const meta = {
  title: 'UI/Selector/GenderSelect',
  component: GenderSelectStory,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  args: {
    initialValue: null,
  },
  argTypes: {
    initialValue: {
      control: { type: 'radio' },
      options: [null, 'M', 'F'],
      description: '초기 선택값 (빈값은 선택안함)',
    },
  },
} satisfies Meta<typeof GenderSelectStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
export const Male: Story = { args: { initialValue: 'M' } }
export const Female: Story = { args: { initialValue: 'F' } }
