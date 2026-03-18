import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { AgreementCheckbox } from '@/components/Auth/agreement-checkbox'

type StoryProps = {
  initialChecked: boolean
  showError?: boolean
}

function AgreementCheckboxStory({ initialChecked }: StoryProps) {
  const [checked, setChecked] = useState(initialChecked)

  return (
    <div className="w-full max-w-md">
      <div className="flex items-center justify-center gap-3 pt-3">
        <AgreementCheckbox id="agree" checked={checked} onChange={setChecked} label="" requiredText=''/>
      </div>
    </div>
  )
}

const meta = {
  title: 'UI/Checkbox',
  component: AgreementCheckboxStory,
  parameters: { layout: 'centered' },
  tags: ['autodocs'],
  args: {
    initialChecked: false,
    showError: true,
  },
  argTypes: {
    initialChecked: { control: 'boolean' },
    showError: { control: 'boolean' },
  },
} satisfies Meta<typeof AgreementCheckboxStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}
export const Checked: Story = { args: { initialChecked: true } }