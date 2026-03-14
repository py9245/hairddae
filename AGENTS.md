# Repository Guidelines

## Project Structure & Module Organization
This repository is split into two main apps:
- `FE/`: React 19 + TypeScript + Vite frontend. Main code is in `FE/src` (`components/`, `lib/`, `App.tsx`, `main.tsx`). Static files are in `FE/public` and deployment config is in `FE/nginx`.
- `BE/`: Spring Boot 3.3 (Java 21) backend. API and config code lives in `BE/src/main/java/com/example/beapp`, app settings in `BE/src/main/resources`, and tests in `BE/src/test/java`.
- `report/`: weekly markdown reports by contributor.

## Build, Test, and Development Commands
Frontend (run in `FE/`):
- `pnpm install`: install dependencies.
- `pnpm dev`: start Vite dev server.
- `pnpm build`: type-check and build production assets.
- `pnpm lint`: run Biome checks.
- `pnpm lint:fix` / `pnpm format`: auto-fix lint and format issues.

Backend (run in `BE/`):
- `./gradlew bootRun` (Windows: `gradlew.bat bootRun`): run API locally.
- `./gradlew test`: run JUnit/Spring tests.
- `docker compose up --build`: run backend stack with Nginx/Postgres/Redis.

## Coding Style & Naming Conventions
Frontend:
- Biome formatting is the source of truth: 2-space indentation, single quotes, semicolons as needed.
- Prefer TypeScript `PascalCase` for React components (e.g., `HealthCard.tsx`), `camelCase` for functions/variables, and `kebab-case` for non-component file names.

Backend:
- Follow standard Java conventions: 4-space indentation, `PascalCase` classes, `camelCase` methods/fields.
- Keep DTOs under `api/dto/...` and controller classes under `api/...Controller`.

## Testing Guidelines
- Backend uses JUnit Platform via `spring-boot-starter-test`; place tests under mirrored package paths in `BE/src/test/java`.
- Name test classes `*Tests` (existing pattern: `BeAppApplicationTests`).
- Frontend test tooling is not configured yet; if added, place tests beside source as `*.test.ts(x)`.

## Commit & Pull Request Guidelines
- Use Conventional Commit prefixes where possible (`feat:`, `docs:`, `delete:`), as seen in history.
- Keep commit messages short and scoped to one change.
- PRs should include: purpose summary, changed area (`FE`/`BE`), related issue/ticket, and screenshots for UI changes.
- Select the MR template by primary change area:
- `FE_template`: `FE/**` 중심 변경
- `BE_Infra_template`: `BE/**`, `BE/nginx/**`, 백엔드/인프라 설정 중심 변경
- `Docs_template`: `report/**`, `docs/**`, root `README.md` 중심 변경
- If code and docs are mixed, use the code template for the primary area.
- Ensure lint/tests pass before requesting review.

## Security & Configuration Tips
- Do not commit secrets. Use `.env` for local credentials and `application.yml` placeholders for runtime variables.
- Review security-related updates in `BE/src/main/java/com/example/beapp/config/SecurityConfig.java` carefully.
