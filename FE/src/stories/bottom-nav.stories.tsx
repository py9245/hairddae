import type { Meta, StoryObj } from '@storybook/react-vite'
import React, { useEffect, useState } from 'react'
import { BottomNavBase } from '@/components/bottom-nav'

function BottomNavOnly({
  pathname,
  interactive = false,
}: {
  pathname: string
  interactive?: boolean
}) {
  const [currentPathname, setCurrentPathname] = useState(pathname)

  useEffect(() => {
    setCurrentPathname(pathname)
  }, [pathname])

  return (
    <BottomNavBase
      interactive={false}
      pathname={currentPathname}
      onNavigate={interactive ? setCurrentPathname : undefined}
    />
  )
}

const meta = {
  title: 'Navigation/BottomNav',
  component: BottomNavBase,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story: () => React.ReactNode) => (
      <div className="relative h-[120px] w-[390px] overflow-hidden bg-white">
        <Story />
      </div>
    ),
  ],
  tags: ['autodocs'],
  args: {
    interactive: true,
    pathname: '/main',
  },
  argTypes: {
    interactive: {
      control: 'boolean',
    },
    pathname: {
      control: 'text',
    },
  },
  render: (args) => (
    <BottomNavOnly
      interactive={args.interactive ?? true}
      pathname={args.pathname ?? '/main'}
    />
  ),
} satisfies Meta<typeof BottomNavBase>

export default meta

type Story = StoryObj<typeof meta>


export const HomeActive: Story = {}

export const MyActive: Story = {
  args: {
    interactive: true,
    pathname: '/mypage',
  },
  render: (args) => (
    <BottomNavOnly
      interactive={args.interactive ?? true}
      pathname={args.pathname ?? '/mypage'}
    />
  ),
}
