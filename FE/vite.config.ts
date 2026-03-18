/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react-swc'
import { playwright } from '@vitest/browser-playwright'
import { defineConfig } from 'vite'

const dirname =
  typeof __dirname !== 'undefined'
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url))
const backendProxyTarget =
  process.env.FE_DEV_BACKEND_PROXY_TARGET ?? 'http://localhost:8080'
const inferenceProxyTarget =
  process.env.FE_DEV_INFERENCE_PROXY_TARGET ?? 'http://127.0.0.1:8090'

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: backendProxyTarget,
        changeOrigin: true,
        secure: false,
      },
      '/ws/inference': {
        target: inferenceProxyTarget,
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      '/rtc/inference': {
        target: inferenceProxyTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/rtc\/inference/, '/rtc'),
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    projects: [
      {
        extends: true,
        plugins: [
          // The plugin will run tests for the stories defined in your Storybook config
          // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
          storybookTest({
            configDir: path.join(dirname, '.storybook'),
          }),
        ],
        test: {
          name: 'storybook',
          browser: {
            enabled: true,
            headless: true,
            provider: playwright({}),
            instances: [
              {
                browser: 'chromium',
              },
            ],
          },
          setupFiles: ['.storybook/vitest.setup.ts'],
        },
      },
    ],
  },
})
