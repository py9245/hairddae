import type { Meta, StoryObj } from '@storybook/react-vite'
import { Download } from 'lucide-react'

function HairSelectorDownloadButtonStory() {
  return (
    <div className="flex min-h-screen items-end justify-center bg-black px-4 pb-10">
      <div className="bg-gradient-to-t from-black/80 via-black/45 to-transparent px-4 pb-6 pt-16">
        <div className="relative flex items-center justify-center">
          <div className="pointer-events-none absolute inset-y-0 left-1/2 z-10 w-24 -translate-x-1/2 rounded-full border border-white/30" />

          <button
            type="button"
            aria-label="캡처 다운로드"
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
  parameters: {
    layout: 'fullscreen',
  },
} satisfies Meta<typeof HairSelectorDownloadButtonStory>

export default meta

type Story = StoryObj<typeof meta>


export const Default: Story = {
  name: ' ',
}