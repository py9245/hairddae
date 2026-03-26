import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect, useState } from 'react'

import { CategoryBottomSheet } from '@/components/ui/category-bottom-sheet'

const sampleCategories = [
  {
    categoryID: 'food',
    categoryName: '식품',
    image: '/hiar-style/style-01-image.png',
  },
  {
    categoryID: 'beauty',
    categoryName: '뷰티',
    image: '/icon/avatar-profile-01.svg',
  },
  {
    categoryID: 'fashion',
    categoryName: '패션',
    image: '/icon/avatar-profile-02.svg',
  },
  {
    categoryID: 'living',
    categoryName: '홈리빙',
    image: '/icon/avatar-profile-03.svg',
  },
  {
    categoryID: 'digital',
    categoryName: '전자기기',
    image: '/icon/avatar-profile-04.svg',
  },
  {
    categoryID: 'hobby',
    categoryName: '취미',
    image: '/icon/avatar-profile-05.svg',
  },
] as const

function CategoryBottomSheetPreview({
  initialOpen = true,
  initialSelectedCategory = sampleCategories[0]?.categoryID ?? '',
  categories = [...sampleCategories],
}: {
  initialOpen?: boolean
  initialSelectedCategory?: string
  categories?: {
    categoryID: string
    categoryName: string
    image: string
  }[]
}) {
  const [open, setOpen] = useState(initialOpen)
  const [selectedCategory, setSelectedCategory] = useState(
    initialSelectedCategory,
  )

  useEffect(() => {
    setOpen(initialOpen)
  }, [initialOpen])

  useEffect(() => {
    setSelectedCategory(initialSelectedCategory)
  }, [initialSelectedCategory])

  return (
    <div className="app-frame relative w-[390px] overflow-hidden bg-bg-primary">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-full bg-primary-50 px-4 py-2 text-sm font-medium text-primary-300"
        >
          시트 열기
        </button>
        <CategoryBottomSheet
          open={open}
          onClose={() => setOpen(false)}
          categories={categories}
          selectedCategory={selectedCategory}
          onSelect={(categoryID) => {
            setSelectedCategory(categoryID)
          }}
        />
    </div>
  )
}

const meta = {
  title: 'UI/Sheet/CategoryBottomSheet',
  component: CategoryBottomSheet,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onClose: {
      table: {
        disable: true,
      },
    },
    onSelect: {
      table: {
        disable: true,
      },
    },
    className: {
      table: {
        disable: true,
      },
    },
  },
  args: {
    open: true,
    onClose: () => {},
    categories: [...sampleCategories],
    selectedCategory: sampleCategories[0].categoryID,
    onSelect: () => {},
  },
} satisfies Meta<typeof CategoryBottomSheet>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: (args) => (
    <CategoryBottomSheetPreview
      initialOpen={args.open}
      initialSelectedCategory={args.selectedCategory}
      categories={args.categories}
    />
  ),
}
