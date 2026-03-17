import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { BirthDatePicker } from '@/components/Auth/birth-date-picker'

type StoryProps = {
  initialValue: string
  hasError: boolean
}

function BirthDatePickerStory({ initialValue, hasError }: StoryProps) {
  const [value, setValue] = useState(initialValue)
  return (
    <div className="w-[200px]">
      <BirthDatePicker
        value={value}
        onChange={setValue}
        onBlur={() => { }}
        hasError={hasError}
      />
    </div>
  )
}

const meta = {
  title: 'UI/DatePicker/BirthDatePicker',
  component: BirthDatePickerStory,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  args: {
    initialValue: '',
    hasError: false,
  },
  argTypes: {
    initialValue: {
      control: { type: 'text' },
      description: '초기 날짜 값 (YYYY-MM-DD 형식, 빈값은 미선택)',
    },
    hasError: {
      control: { type: 'boolean' },
      description: '에러 상태 (빨간 테두리)',
    },
  },
} satisfies Meta<typeof BirthDatePickerStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
export const WithValue: Story = { args: { initialValue: '1995-05-15' } }
export const WithError: Story = { args: { hasError: true } }
