/// <reference types="vitest/config" />
import fs from 'node:fs'
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
const projectStaticRoot = path.resolve(dirname, '../static')
const backendProxyTarget =
  process.env.FE_DEV_BACKEND_PROXY_TARGET ?? 'http://localhost:8080'
const inferenceProxyTarget =
  process.env.FE_DEV_INFERENCE_PROXY_TARGET ?? 'http://127.0.0.1:8090'
const httpsCertPath = process.env.FE_DEV_HTTPS_CERT_FILE
const httpsKeyPath = process.env.FE_DEV_HTTPS_KEY_FILE
const httpsOptions =
  httpsCertPath && httpsKeyPath
    ? {
        cert: fs.readFileSync(path.resolve(dirname, httpsCertPath)),
        key: fs.readFileSync(path.resolve(dirname, httpsKeyPath)),
      }
    : undefined

function contentTypeForFile(filePath: string) {
  const extension = path.extname(filePath).toLowerCase()
  switch (extension) {
    case '.json':
      return 'application/json; charset=utf-8'
    case '.png':
      return 'image/png'
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg'
    case '.webp':
      return 'image/webp'
    case '.svg':
      return 'image/svg+xml'
    case '.txt':
      return 'text/plain; charset=utf-8'
    default:
      return 'application/octet-stream'
  }
}

function serveProjectStaticDir() {
  return {
    name: 'serve-project-static-dir',
    configureServer(server: import('vite').ViteDevServer) {
      server.middlewares.use((req, res, next) => {
        const rawUrl = req.url?.split('?')[0] ?? ''
        if (!rawUrl.startsWith('/static/')) {
          next()
          return
        }

        const relativePath = decodeURIComponent(rawUrl.slice('/static/'.length))
        const filePath = path.resolve(projectStaticRoot, relativePath)
        if (!filePath.startsWith(projectStaticRoot)) {
          res.statusCode = 403
          res.end('Forbidden')
          return
        }
        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          next()
          return
        }

        res.setHeader('Content-Type', contentTypeForFile(filePath))
        fs.createReadStream(filePath).pipe(res)
      })
    },
  }
}

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig({
  plugins: [react(), tailwindcss(), serveProjectStaticDir()],
  server: {
    https: httpsOptions,
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
