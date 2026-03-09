# Repository Guidelines

## Project Structure & Module Organization
- `FE/`: Frontend application (React + TypeScript + Vite).
  - `FE/src/`: App source code (`main.tsx`, `App.tsx`, styles).
  - `FE/public/`: Static assets served as-is.
  - `FE/eslint.config.js`, `FE/tsconfig*.json`, `FE/vite.config.ts`: lint/build/tooling config.
- `report/`: Weekly individual reports (Markdown) linked from root `README.md`.
- Root `README.md`: project overview and report links.

Keep feature code inside `FE/src/` and avoid mixing report artifacts with runtime source files.

## Build, Test, and Development Commands
Run commands from `FE/`.

- `pnpm dev`: start local dev server with HMR.
- `pnpm build`: type-check (`tsc -b`) and produce production bundle.
- `pnpm preview`: serve the built bundle locally.
- `pnpm lint`: run ESLint over the frontend codebase.

Example:
```bash
cd FE
pnpm dev
```

## Coding Style & Naming Conventions
- Language: TypeScript + React function components.
- Indentation: 2 spaces; keep imports grouped and unused code removed.
- Components/files: `PascalCase` for components, `camelCase` for variables/functions, kebab/lowercase for non-component asset names.
- Follow ESLint rules in `FE/eslint.config.js`; run `pnpm lint` before commit.

## Testing Guidelines
- No automated test framework is configured yet in this repository.
- Minimum quality gate today: successful `pnpm lint` and `pnpm build`.
- When adding tests, place them near source files as `*.test.ts` / `*.test.tsx` and document the test command in `FE/package.json`.

## Commit & Pull Request Guidelines
Git history shows short conventional prefixes (`feat:`, `docs:`, `delete:`) and scoped report commits. Prefer:
- `feat: add onboarding camera step`
- `docs: update week1 report links`

PRs should include:
- clear summary of changes and affected paths,
- linked issue/ticket (e.g., Jira key),
- screenshots or short clips for UI changes,
- confirmation that `pnpm lint` and `pnpm build` passed.

## Security & Configuration Tips
- Do not commit secrets, API keys, or private credentials in Markdown or source.
- Use environment files (for future backend/API integration) and keep them out of version control.
