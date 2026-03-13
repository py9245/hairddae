# 심미진 Week2 Report

## 260309
- 기존 FE 프로젝트 정리
  - 기존 JavaScript 기반 Front-end 프로젝트와 관련 설정 파일을 삭제하고, 프론트엔드 구조를 처음부터 다시 정비함.
  - 사용하지 않게 된 배포 설정, Jenkinsfile, 기존 엔트리 파일과 의존성 파일을 제거해 새 코드베이스를 올릴 수 있는 상태로 정리함.

- FE 프로젝트 재초기화
  - React 19 + TypeScript + Vite 기반으로 FE 프로젝트를 새로 구성함.
  - `pnpm` 기반 패키지 관리 환경, `tsconfig`, `vite.config`, 기본 엔트리 파일(`main.tsx`, `App.tsx`)과 초기 README, `.gitignore`를 세팅함.
  - JSX 기반 구조를 TSX 기반 구조로 전환해 이후 타입 안정성을 확보할 수 있는 기반을 마련함.

- 협업 템플릿 및 저장소 규칙 문서화
  - GitLab Merge Request 템플릿을 추가해 작업 배경, 변경 사항, 테스트 여부를 공통 형식으로 정리할 수 있도록 함.
  - 저장소 작업 규칙 문서인 `AGENTS.md`를 추가해 프로젝트 구조, 명령어, 스타일 규칙, 협업 기준을 문서화함.

- FE 라이브러리 셋업 및 공통 스타일 기반 구성
  - Biome 설정을 추가해 코드 포맷팅 및 정적 점검 기준을 정리함.
  - `components.json`을 추가해 shadcn-ui 계열 컴포넌트 구성을 위한 기반을 세팅함.
  - Tailwind 기반 전역 스타일과 CSS 변수 토큰을 `index.css`에 구성해 색상, radius, dark mode 대응이 가능한 기본 테마 구조를 마련함.
  - `main.tsx`에서 루트 엘리먼트 존재 여부를 명시적으로 검사하도록 수정해 초기 렌더링 안정성을 보강함.

- 컴포넌트 개발 상세
  - 공통 버튼 컴포넌트 개발
    - `src/components/ui/button.tsx`에 재사용 가능한 `Button` 컴포넌트를 추가함.
    - `variant`(`default`, `destructive`, `outline`, `secondary`, `ghost`, `link`)와 `size`(`default`, `sm`, `lg`, `icon`) 조합을 지원하도록 구성함.
    - `asChild` 패턴을 지원해 버튼 태그 외 다른 엘리먼트에도 동일 스타일을 적용할 수 있게 설계함.
    - `class-variance-authority`, `@radix-ui/react-slot`을 활용해 스타일 조합과 확장성을 확보함.
  - 공통 유틸 함수 개발
    - `src/lib/utils.ts`에 `cn` 유틸 함수를 추가함.
    - `clsx`와 `tailwind-merge`를 조합해 조건부 클래스 처리와 Tailwind 클래스 병합을 일관되게 사용할 수 있도록 함.
  - 앱 초기 확인 화면 구성
    - `src/App.tsx`에서 공통 `Button` 컴포넌트를 불러와 화면 중앙에 렌더링하도록 구성함.
    - 라이브러리와 스타일 세팅이 정상 동작하는지 확인할 수 있는 최소 화면으로 활용함.

- Storybook 및 Vitest 연동 환경 구축
  - `.storybook/main.ts`, `.storybook/preview.ts`, `.storybook/vitest.setup.ts`를 추가해 Storybook + Vitest 기반 UI 문서화 및 테스트 환경을 세팅함.
  - 접근성(a11y), docs, onboarding, Vitest addon을 함께 구성해 추후 컴포넌트 문서화와 검증 확장이 가능하도록 함.
  - Storybook 전역에서 `src/index.css`를 불러와 앱과 동일한 스타일 기준으로 스토리를 확인할 수 있게 맞춤.


## 260310
- Storybook 예제 컴포넌트 개발 상세
  - `src/stories/Button.tsx`
    - Storybook 학습 및 테스트용 버튼 예제 컴포넌트를 추가함.
    - `primary`, `size`, `backgroundColor`, `label`, `onClick` props를 받아 버튼 상태를 조합해 확인할 수 있도록 구성함.
  - `src/stories/Header.tsx`
    - 로그인/로그아웃 상태에 따라 다른 액션 버튼을 노출하는 헤더 예제 컴포넌트를 추가함.
    - 사용자 정보(`user`) 유무에 따라 `Log in`, `Log out`, `Sign up` 버튼을 다르게 렌더링하도록 구성함.


## 260311
  - `src/stories/Page.tsx`
    - `Header`를 포함하는 페이지 단위 예제 컴포넌트를 추가함.
    - 내부 상태로 로그인 여부를 관리해 페이지 단위 인터랙션 흐름을 확인할 수 있도록 구성함.
  - `src/stories/*.stories.ts`
    - `Button`, `Header`, `Page` 각각에 대한 Storybook 스토리를 추가함.
    - `Button` 스토리에서는 Primary, Secondary, Large, Small 상태를 분리해 확인 가능하도록 구성함.
    - `Header` 스토리에서는 LoggedIn, LoggedOut 상태를 구분해 사용자 상태별 UI를 확인할 수 있게 함.
    - `Page` 스토리에서는 `play` 함수를 사용해 로그인 버튼 클릭 후 로그아웃 버튼이 나타나는 흐름을 테스트할 수 있도록 설정함.


## 260312
- 발표 장표 준비
