import type { Meta, StoryObj } from '@storybook/react-vite'
import { CategoryCard } from '@/components/ui/category-card'

const meta = {
  title: 'UI/Card/CategoryCard',
  component: CategoryCard,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  args: {
    label: '단발',
  },
} satisfies Meta<typeof CategoryCard>

export default meta

type Story = StoryObj<typeof meta>

function CenteredPreview(args: Story['args']) {
  return (
    <div className="w-full max-w-md">
      <div className="flex items-center justify-center gap-3 pt-3">
        <CategoryCard {...args} />
      </div>
    </div>
  )
}

export const Default: Story = {
  parameters: {
    docs: {
      description: {
        story: '기본 상태입니다.',
      },
    },
  },
  render: (args) => <CenteredPreview {...args} />,
}

export const OverFiveChars: Story = {
  args: {
    label: '허쉬레이어펌',
  },
  parameters: {
    docs: {
      description: {
        story: '긴 라벨이 폭 기준으로 자동 줄바꿈되는지 확인합니다.',
      },
    },
  },
  render: (args) => <CenteredPreview {...args} />,
}

export const WithSpaces: Story = {
  args: {
    label: '허쉬 레이어 펌',
  },
  parameters: {
    docs: {
      description: {
        story: '공백이 있는 라벨이 원문 그대로 표시되면서 자동 줄바꿈되는지 확인합니다.',
      },
    },
  },
  render: (args) => <CenteredPreview {...args} />,
}

export const Comparison: Story = {
  parameters: {
    docs: {
      description: {
        story: '길이에 따른 자동 줄바꿈 동작을 한 화면에서 비교합니다.',
      },
    },
  },
  render: () => (
    <div className="w-full max-w-md">
      <div className="flex items-start justify-center gap-4 pt-3">
        <div className="flex w-[96px] justify-center">
          <CategoryCard label="단발" />
        </div>
        <div className="flex w-[96px] justify-center">
          <CategoryCard label="허쉬레이어펌" />
        </div>
        <div className="flex w-[96px] justify-center">
          <CategoryCard label="허쉬 레이어 펌" />
        </div>
      </div>
    </div>
  ),
}
