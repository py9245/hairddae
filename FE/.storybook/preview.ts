import type { Preview } from '@storybook/react-vite'
import '../src/index.css'
import { createElement } from 'react'

const preview: Preview = {
  decorators: [
    (Story) =>
      createElement(
        'div',
        { className: 'app-frame-shell' },
        createElement('div', { className: 'app-frame' }, createElement(Story)),
      ),
  ],
  parameters: {
    layout: 'fullscreen',
    backgrounds: {
      default: 'app-bg',
      values: [
        {
          name: 'app-bg',
          value: '#f5f5f5', // --bg-primary
        },
        {
          name: 'light',
          value: '#f5f5f5',
        },
        {
          name: 'dark',
          value: '#333333',
        },
      ],
    },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: 'todo',
    },
  },
}

export default preview