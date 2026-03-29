import type { Meta, StoryObj } from '@storybook/react-vite'
import { fn } from 'storybook/test'
import { HairSelectorItem } from '@/components/ui/hair-selector-item'
import type { HairItem } from '@/lib/Camera/HairItem'

const emptyHairItem: HairItem = {
  id: 0,
  image: '',
  label: 'None',
}

const sampleHairItem: HairItem = {
  id: 1,
  image: '/hair/hair.png',
  label: 'Hair 1',
}

const meta = {
  title: 'UI/Selector/HairSelectorItem',
  component: HairSelectorItem,
  tags: ['autodocs'],
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: `
카메라 화면 하단 셀렉터에 사용되는 개별 헤어 아이템 버튼입니다.

- 선택 상태에 따라 썸네일 크기와 강조 스타일이 달라집니다.
- 비활성화 상태를 지원합니다.
- 빈 아이템(id 0)은 금지 아이콘으로 렌더링됩니다.
        `,
      },
    },
  },
  decorators: [
    (Story) => (
      <div className="bg-black px-6 py-10">
        <Story />
      </div>
    ),
  ],
  args: {
    item: sampleHairItem,
    selected: false,
    disabled: false,
    onClick: fn(),
  },
  argTypes: {
    item: {
      control: 'object',
      description: '헤어 아이템 데이터입니다.',
      table: {
        type: { summary: 'HairItem' },
      },
    },
    selected: {
      control: 'boolean',
      description: '선택 여부입니다.',
      table: {
        type: { summary: 'boolean' },
      },
    },
    disabled: {
      control: 'boolean',
      description: '비활성화 여부입니다.',
      table: {
        type: { summary: 'boolean' },
        defaultValue: { summary: 'false' },
      },
    },
    onClick: {
      description: '아이템 클릭 시 실행되는 콜백 함수입니다.',
      action: 'clicked',
      table: {
        type: { summary: '() => void' },
      },
    },
  },
} satisfies Meta<typeof HairSelectorItem>

export default meta

type Story = StoryObj<typeof meta>

export const Default: Story = {
  parameters: {
    docs: {
      description: {
        story: '기본 비선택 헤어 아이템 상태입니다.',
      },
    },
  },
}

export const Selected: Story = {
  args: {
    selected: true,
  },
  parameters: {
    docs: {
      description: {
        story: '선택된 헤어 아이템 상태입니다.',
      },
    },
  },
}

export const Disabled: Story = {
  args: {
    disabled: true,
  },
  parameters: {
    docs: {
      description: {
        story: '비활성화된 헤어 아이템 상태입니다.',
      },
    },
  },
}

export const Empty: Story = {
  args: {
    item: emptyHairItem,
  },
  parameters: {
    docs: {
      description: {
        story: '헤어를 선택하지 않는 빈 아이템 상태입니다.',
      },
    },
  },
}
