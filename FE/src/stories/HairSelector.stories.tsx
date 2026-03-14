import type { Meta, StoryObj } from '@storybook/react-vite'
import type { ComponentProps } from 'react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { HairSelector } from '../components/Camera/HairSelector'

type HairSelectorProps = ComponentProps<typeof HairSelector>
type HairItem = HairSelectorProps['items'][number]

function createHairThumb(label: string, fill: string, accent: string) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">
      <circle cx="48" cy="48" r="48" fill="${fill}" />
      <path d="M22 38c0-16 12-24 26-24s26 8 26 24v18c0 12-9 20-26 20s-26-8-26-20V38Z" fill="${accent}" />
      <circle cx="38" cy="46" r="4" fill="white" fill-opacity="0.85" />
      <circle cx="58" cy="46" r="4" fill="white" fill-opacity="0.85" />
      <path d="M36 61c4 4 20 4 24 0" stroke="white" stroke-width="4" stroke-linecap="round" />
      <text x="48" y="88" text-anchor="middle" fill="white" font-size="12" font-family="Arial, sans-serif">${label}</text>
    </svg>
  `

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

const hairItems: HairItem[] = [
  {
    id: 0,
    label: 'Original',
    img: '',
    thumb: '',
  },
  {
    id: 1,
    label: 'Soft',
    img: createHairThumb('Soft', '#F3E8FF', '#7C3AED'),
    thumb: createHairThumb('Soft', '#F3E8FF', '#7C3AED'),
  },
  {
    id: 2,
    label: 'Wave',
    img: createHairThumb('Wave', '#E0F2FE', '#0284C7'),
    thumb: createHairThumb('Wave', '#E0F2FE', '#0284C7'),
  },
  {
    id: 3,
    label: 'Bob',
    img: createHairThumb('Bob', '#FDE68A', '#B45309'),
    thumb: createHairThumb('Bob', '#FDE68A', '#B45309'),
  },
  {
    id: 4,
    label: 'Pixie',
    img: createHairThumb('Pixie', '#DCFCE7', '#15803D'),
    thumb: createHairThumb('Pixie', '#DCFCE7', '#15803D'),
  },
  {
    id: 5,
    label: 'Perm',
    img: createHairThumb('Perm', '#FFE4E6', '#E11D48'),
    thumb: createHairThumb('Perm', '#FFE4E6', '#E11D48'),
  },
]

function HairSelectorPreview(args: HairSelectorProps) {
  const [selectedId, setSelectedId] = useState(args.selectedId)

  useEffect(() => {
    setSelectedId(args.selectedId)
  }, [args.selectedId])

  const selectedItem =
    args.items.find((item) => item.id === selectedId) ?? args.items[0]

  return (
    <div className="flex min-h-[760px] items-center justify-center bg-[radial-gradient(circle_at_top,_#2b3443,_#0f172a_55%,_#020617)] p-6">
      <div className="relative h-[720px] w-full max-w-[390px] overflow-hidden rounded-[32px] border border-white/15 bg-slate-950 shadow-2xl">
        <div className="absolute inset-0 bg-[linear-gradient(180deg,_rgba(255,255,255,0.1),_transparent_24%),linear-gradient(160deg,_rgba(14,165,233,0.18),_transparent_45%),linear-gradient(20deg,_rgba(249,115,22,0.18),_transparent_40%)]" />

        <div className="relative flex h-full flex-col px-5 pt-6">
          <div className="rounded-3xl border border-white/10 bg-black/20 p-4 text-white backdrop-blur-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-white/55">
              Camera / Hair Selector
            </p>
            <div className="mt-3 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-white/60">Current style</p>
                <p className="text-2xl font-semibold">
                  {selectedItem?.label ?? 'Original'}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setSelectedId(0)}
                >
                  Reset
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    const selectableItems = args.items.filter(
                      (item) => item.id !== selectedId,
                    )
                    const nextItem =
                      selectableItems[
                        Math.floor(Math.random() * selectableItems.length)
                      ]

                    if (nextItem) {
                      setSelectedId(nextItem.id)
                    }
                  }}
                >
                  Random
                </Button>
              </div>
            </div>
          </div>

          <div className="relative mt-6 flex-1 overflow-hidden rounded-[28px] border border-white/10 bg-white/5">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.16),_transparent_36%),linear-gradient(180deg,_rgba(15,23,42,0.1),_rgba(15,23,42,0.7))]" />
            <div className="relative flex h-full items-center justify-center">
              <div className="absolute top-7 rounded-full border border-white/15 bg-black/20 px-3 py-1 text-xs text-white/70 backdrop-blur-sm">
                Swipe or tap to choose a style
              </div>

              <div className="h-72 w-52 rounded-[44px] border border-white/10 bg-[radial-gradient(circle_at_top,_#fde68a,_#fb7185_40%,_#1e293b)] shadow-[0_30px_80px_rgba(0,0,0,0.45)]" />
            </div>

            <HairSelector
              {...args}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id)
                args.onSelect(id)
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

const meta = {
  title: 'Camera/HairSelector',
  component: HairSelector,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  args: {
    items: hairItems,
    selectedId: 2,
    onSelect: () => {},
  },
  render: (args) => <HairSelectorPreview {...args} />,
} satisfies Meta<typeof HairSelector>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const EmptySelected: Story = {
  args: {
    selectedId: 0,
  },
}
