# React + TypeScript + Vite

## Local env

로컬 개발 시에는 [`FE/.env.example`](/home/yusin/S14P21M101/FE/.env.example) 를 복사해 `FE/.env` 로 사용한다.

중요:

- `FE_DEV_BACKEND_PROXY_TARGET`, `FE_DEV_INFERENCE_PROXY_TARGET` 는 Vite dev server 프로세스만 읽는 값이라 브라우저 번들에 노출되지 않는다.
- inference 서버 IP 같은 민감한 운영 라우팅 값은 `VITE_*` 로 두지 않는다.
- 브라우저는 항상 same-origin `/api`, `/ws/inference` 로만 통신하고, 실제 upstream host 는 nginx 또는 Vite proxy 가 대신 결정한다.

## Static Deploy

- 정적 배포 산출물은 `pnpm.cmd build` 후 생성되는 `FE/dist` 이다.
- 운영 배포 시 브라우저는 same-origin 기준으로 `/api`, `/ws/inference`, `/rtc/inference` 로만 통신한다.
- 운영 nginx 는 정적 파일을 서빙하면서 위 3개 경로를 각각 backend / inference upstream 으로 프록시해야 한다.
- FE 단독 nginx 예시는 [`FE/nginx/default.conf`](/C:/Users/SSAFY/Desktop/TTT/S14P21M101/FE/nginx/default.conf) 에 있다.
- 현재 레포 기준 운영 도메인은 `j14m101.p.ssafy.io` 이며, Jenkins 는 `FE/dist` 를 서버의 nginx html 디렉터리로 rsync 한다.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is currently not compatible with SWC. See [this issue](https://github.com/vitejs/vite-plugin-react/issues/428) for tracking the progress.

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

