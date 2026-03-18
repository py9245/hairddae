import type { Meta, StoryObj } from '@storybook/react-vite'
import { Download } from 'lucide-react'
import { fn } from 'storybook/test'

function HairSelectorDownloadButtonStory({
  onDownload,
}: {
  onDownload?: () => void
}) {
  return (
    <div className="flex min-h-screen items-end justify-center bg-black px-4 pb-10">
      <div className="bg-gradient-to-t from-black/80 via-black/45 to-transparent px-4 pb-6 pt-16">
        <div className="relative flex items-center justify-center">
          <div className="pointer-events-none absolute inset-y-0 left-1/2 z-10 w-24 -translate-x-1/2 rounded-full border border-white/30" />

          <button
            type="button"
            aria-label="캡처 다운로드"
            title="캡처 다운로드"
            onClick={onDownload}
            className="relative z-20 flex items-center justify-center"
          >
            <div className="relative flex h-24 w-24 items-center justify-center overflow-hidden rounded-full border border-white bg-white shadow-[0_0_0_6px_rgba(255,255,255,0.25)] transition-all duration-300">
              <Download className="h-10 w-10 text-slate-700" />
            </div>
          </button>
        </div>
      </div>
    </div>
  )
}

const meta = {
  title: 'UI/Button/HairSelectorDownloadButton',
  component: HairSelectorDownloadButtonStory,
  tags: ['autodocs'],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: `
헤어 선택 영역에서 프리즈 상태일 때 노출되는 다운로드 버튼입니다.

- 현재 화면을 캡처하거나 저장하는 액션에 사용됩니다.
- 원형 강조 UI 안에 다운로드 아이콘을 배치했습니다.
     `,
      },
    },
  },
  args: {
    onDownload: fn(),
  },
  argTypes: {
    onDownload: {
      description: '다운로드 버튼 클릭 시 실행되는 콜백 함수',
      action: 'clicked',
      table: {
        type: { summary: '() => void' },
      },
    },
  },
} satisfies Meta<typeof HairSelectorDownloadButtonStory>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  name: 'ImageDownload',
  parameters: {
    docs: {
      description: {
        story: '기본 다운로드 버튼 상태입니다.',
      },
    },
  },
}