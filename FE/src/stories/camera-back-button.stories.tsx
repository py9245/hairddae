import type { Meta, StoryObj } from '@storybook/react-vite'
import { X } from 'lucide-react'
import { fn } from 'storybook/test'

function TopButtonsDemo({
  onBack,
}: {
  onBack?: () => void
}) {
  return (
    <div className="bg-black p-4">
      <button
        type="button"
        aria-label="메인 페이지로 이동"
        title="메인 페이지로 이동"
        onClick={onBack}
        className="flex h-11 w-11 items-center justify-center text-white/85 transition hover:text-white"
      >
        <X className="h-10 w-10" />
      </button>
    </div>
  )
}

const meta = {
  title: 'UI/Button/CameraBackButton',
  component: TopButtonsDemo,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
카메라 화면 상단에 위치하는 뒤로가기 버튼입니다.

- 메인 페이지로 이동하는 액션에 사용됩니다.
- 아이콘 버튼 형태로 제공됩니다.
- 어두운 배경 위에서 사용하는 것을 기준으로 스타일링되어 있습니다.
        `,
      },
    },
  },
  args: {
    onBack: fn(),
  },
  argTypes: {
    onBack: {
      description: '뒤로가기 버튼 클릭 시 실행되는 콜백 함수',
      action: 'clicked',
      table: {
        type: { summary: '() => void' },
      },
    },
  },
} satisfies Meta<typeof TopButtonsDemo>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: 'MoveMainPage',
  parameters: {
    docs: {
      description: {
        story: '기본 뒤로가기 버튼 상태입니다.',
      },
    },
  },
}