# 새 페이지 생성기

**인수**: $ARGUMENTS

$ARGUMENTS에 페이지 설명을 넣으면 페이지 컴포넌트 생성 + 라우터 설정까지 완성합니다.

예시:
- `/new-page 알림 페이지 — 보호, 뒤로가기 헤더, 바텀 내비 없음`
- `/new-page 헤어스타일 상세 페이지 — 보호, 뒤로가기 헤더, 바텀 내비 없음`
- `/new-page 회원가입 완료 페이지 — 공개, 바텀 내비 없음`

---

## Step 1 — 컨텍스트 파일 읽기

생성 전에 반드시 아래 4개 파일을 읽는다:

1. `src/router.tsx` — 현재 경로 유니온 타입(`createProtectedRoute` 파라미터), routeTree 구조
2. `src/app/main.tsx` — 스크롤 보호 페이지 표준 패턴
3. `src/app/login.tsx` — 공개(인증 전) 페이지 표준 패턴
4. `src/components/bottom-nav.tsx` — `BottomNavRoute` 유니온, `shouldHideBottomNav`, `items` 배열

---

## Step 2 — 페이지 파라미터 결정

`$ARGUMENTS`에서 추론한다. 모호하면 사용자에게 질문한다.

| 파라미터 | 추론 방법 |
|---------|---------|
| 컴포넌트명 | PascalCase, 예: `NotificationPage` |
| 파일명 | kebab-case, 예: `notification` |
| 라우트 경로 | 소문자 단어, 예: `notification` |
| 인증 보호 여부 | "보호" 키워드 → `createProtectedRoute`, "공개" → auth 하위 또는 루트 |
| 바텀 내비 표시 여부 | "바텀 내비 없음" → `shouldHideBottomNav`에 포함 안 함 |
| 헤더 모드 | "뒤로가기 헤더" → 3컬럼 모드, "로고" → 로고 모드 |

---

## Step 3 — 페이지 파일 생성

`src/app/{file-name}.tsx`에 생성한다.

### 템플릿 A: 스크롤 보호 페이지 (바텀 내비 있음)

```tsx
import { Header } from '@/components/header'

export default function ComponentName() {
  return (
    <main className="app-frame-page h-full overflow-y-auto bg-neutral-500 pb-[108px] text-text-warm-500">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="헤어때" labelClassName="text-primary-300 tracking-[-0.04em]" />
        {/* 콘텐츠 */}
      </div>
    </main>
  )
}
```

### 템플릿 B: 서브페이지 (뒤로가기 헤더, absolute → `pt-16` 필수)

```tsx
import { useRouter } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { Header } from '@/components/header'

export default function ComponentName() {
  const router = useRouter()

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <Header
        leftAction={
          <button
            type="button"
            onClick={() => router.history.back()}
            aria-label="뒤로 가기"
          >
            <ChevronLeft className="size-6" />
          </button>
        }
        centerContent={
          <h1 className="text-base font-semibold text-text-dark">페이지 제목</h1>
        }
      />
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-16">
        {/* 콘텐츠 */}
      </div>
    </main>
  )
}
```

### 템플릿 C: 서브페이지, 바텀 내비 없음 (뒤로가기 헤더)

```tsx
import { useRouter } from '@tanstack/react-router'
import { ChevronLeft } from 'lucide-react'
import { Header } from '@/components/header'

export default function ComponentName() {
  const router = useRouter()

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary">
      <Header
        leftAction={
          <button
            type="button"
            onClick={() => router.history.back()}
            aria-label="뒤로 가기"
          >
            <ChevronLeft className="size-6" />
          </button>
        }
        centerContent={
          <h1 className="text-base font-semibold text-text-dark">페이지 제목</h1>
        }
      />
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-16">
        {/* 콘텐츠 */}
      </div>
    </main>
  )
}
```

### 템플릿 D: 공개/인증 전 페이지 (바텀 내비 없음)

```tsx
export default function ComponentName() {
  return (
    <main className="app-frame-page flex flex-col items-center justify-center bg-bg-primary px-6 py-10">
      <div className="w-full max-w-md">
        {/* 콘텐츠 */}
      </div>
    </main>
  )
}
```

### 코딩 규칙

- raw hex 금지 — 모든 색상은 Tailwind 토큰 클래스
- 모든 UI 문자열은 한국어
- 사용하는 것만 import (미사용 import 없음)
- `type` 키워드 사용 (interface 아님)
- 이미지에는 `draggable={false}` 추가
- 접근성: `aria-label`, `aria-current`, `role="alert"` 적절히 사용

---

## Step 4 — 라우터 업데이트 (`src/router.tsx`)

### 보호 페이지 (protected route)

```tsx
// 1. 파일 상단 import 추가
import NewPage from '@/app/{file-name}'

// 2. createProtectedRoute 경로 유니온 타입 확장
function createProtectedRoute(
  path: 'main' | 'camera' | 'mypage' | 'hairlist' | 'newpath',
  // ↑ 기존 유니온에 새 경로 추가
  component: () => ReactElement,
)

// 3. 라우트 상수 생성 (기존 라우트 선언 블록에 추가)
const newPageRoute = createProtectedRoute('newpath', NewPageWrapper)
function NewPageWrapper() { return <NewPage /> }

// 4. routeTree에 추가
const routeTree = rootRoute.addChildren([
  splashRoute,
  authRoute.addChildren([loginRoute, signupRoute]),
  mainRoute,
  cameraRoute,
  myPageRoute,
  hairListRoute,
  newPageRoute, // ← 추가
])
```

### 공개 페이지 (auth 하위에 추가)

```tsx
// 1. import 추가
import NewPage from '@/app/{file-name}'

// 2. auth 하위 라우트 생성
const newPageRoute = createRoute({
  getParentRoute: () => authRoute,
  path: 'newpath',
  component: NewPage,
})

// 3. authRoute 하위에 추가
authRoute.addChildren([loginRoute, signupRoute, newPageRoute])
```

---

## Step 5 — 바텀 내비 업데이트 (`src/components/bottom-nav.tsx`)

**바텀 내비에 새 탭을 추가하는 경우에만** 수정한다. 단순히 보호 페이지를 추가하고 바텀 내비에는 표시하지 않을 경우 수정 불필요.

### 바텀 내비 탭을 추가할 때

```tsx
// 1. BottomNavRoute 유니온 확장
type BottomNavRoute = '/main' | '/camera' | '/mypage' | '/newpath'

// 2. items 배열에 추가
import { SomeIcon } from 'lucide-react'

const items: BottomNavItem[] = [
  // ... 기존 항목
  {
    label: '새 탭',
    to: '/newpath',
    icon: SomeIcon,
    match: (pathname) => pathname.startsWith('/newpath'),
  },
]

// 3. shouldHideBottomNav에 경로 추가
function shouldHideBottomNav(pathname: string) {
  return (
    !pathname.startsWith('/main') &&
    !pathname.startsWith('/mypage') &&
    !pathname.startsWith('/hairlist') &&
    !pathname.startsWith('/newpath')  // ← 추가
  )
}
```

---

## Step 6 — 검증 체크리스트

모든 항목을 확인한 후 완료를 보고한다.

- [ ] `src/app/{file-name}.tsx` 생성 완료
- [ ] `src/router.tsx`에 import 추가
- [ ] 라우트 상수(`const newPageRoute`) 생성
- [ ] `routeTree`에 등록
- [ ] `createProtectedRoute` 경로 유니온 타입 확장 (보호 페이지인 경우)
- [ ] 바텀 내비 업데이트 (탭 추가 시에만)
- [ ] raw hex 없음
- [ ] 모든 UI 문자열 한국어
- [ ] 미사용 import 없음
- [ ] `npm run build` 타입 에러 없음 확인 권고
