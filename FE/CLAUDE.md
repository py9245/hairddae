# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Manager

Use **pnpm** for all package operations.

## Commands

```bash
pnpm dev           # Start Vite dev server
pnpm build         # Type-check + production build (outputs to dist/)
pnpm preview       # Preview production build locally (port 4173)
pnpm lint          # Biome lint check
pnpm lint:fix      # Auto-fix lint issues
pnpm format        # Auto-format with Biome
pnpm storybook     # Storybook dev server (port 6006)
pnpm test:e2e      # Playwright e2e tests (requires preview server running)
pnpm test:e2e:ui   # Playwright interactive UI
```

## Local Development Setup

Copy `.env.example` to `.env`. Key env vars:

- `FE_DEV_BACKEND_PROXY_TARGET` — upstream for `/api` (default: `http://localhost:8080`)
- `FE_DEV_INFERENCE_PROXY_TARGET` — upstream for `/ws/inference` and `/rtc/inference` (default: `http://127.0.0.1:8090`)
- `VITE_SIMULATE_LOGIN` / `VITE_SIMULATE_SIGNUP` — bypass real auth in dev
- `FE_DEV_HTTPS_CERT_FILE` / `FE_DEV_HTTPS_KEY_FILE` — optional HTTPS for dev server

**Important**: `FE_DEV_*` variables are Vite server-only and never bundled into the browser. Browser always communicates via same-origin paths (`/api`, `/ws/inference`, `/rtc/inference`); proxying is handled by Vite in dev or nginx in production.

## Architecture

### Routing

TanStack React Router (`src/router.tsx`). Routes are file-organized under `src/app/`. Protected routes use the `createProtectedRoute` helper which redirects unauthenticated users to `/auth/login` (preserving the original location). Route search params are validated with Zod.

Main routes: `/` (splash), `/landing`, `/auth/login`, `/auth/signup`, `/main`, `/camera`, `/mypage`, `/hairlist`

### Authentication

Centralized auth store in `src/lib/auth.ts` with pub/sub listeners. Key API:
- `isAuthenticated()` — sync check
- `ensureAuthenticated()` — throws if not authenticated
- `login()`, `logout()`, `expireSession()`

`apiFetch` in `src/lib/api.ts` wraps `fetch` with automatic token refresh on 401 (calls `/api/accounts/refreshToken/`, retries once). All requests use `credentials: 'include'` (session cookies).

### State Management

- **Server state**: TanStack React Query — queries and mutations live in `src/hooks/` organized by feature (Auth, Camera, Home, MyPage)
- **Client/auth state**: Custom pub/sub store in `src/lib/auth.ts`

### Feature: Camera / Hair Try-On

The camera feature (`src/app/camera/`, `src/lib/Camera/`, `src/hooks/Camera/`) uses:
- WebRTC session managed by `useHairRtcSession` / `useHairRtcDisplay`
- WebSocket inference at `/ws/inference`, WebRTC at `/rtc/inference`
- MediaPipe-based real-time video processing
- Three.js (`three`) for 3D rendering/overlays

### Component Patterns

- `src/components/ui/` — base primitives built on Radix UI with Class Variance Authority (CVA) for variants
- Utility: `cn()` from `src/lib/utils.ts` (clsx + tailwind-merge)
- Path alias `@/` maps to `src/`

### Code Style (Biome)

- 2-space indent, single quotes, no semicolons
- Biome handles both formatting and linting (`biome.json`)
- ESLint is also configured but Biome is the primary tool

### Production Deployment

`pnpm build` → `dist/`. Nginx must proxy `/api` → backend, `/ws/inference` and `/rtc/inference` → inference server. See `nginx/default.conf` for reference config. Jenkins rsync's `dist/` to the server. Production domain: `j14m101.p.ssafy.io`.
