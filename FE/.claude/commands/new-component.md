# 새 컴포넌트 생성기

**인수**: $ARGUMENTS

$ARGUMENTS에 컴포넌트 설명을 넣으면 → 컴포넌트 파일 생성 + design-system.md 업데이트까지 완성합니다.

예시:
- `/new-component 뱃지 컴포넌트 — 상태(성공/경고/에러) 표시, CVA 변형`
- `/new-component 프로필 카드 — 이미지 + 이름 + 팔로우 버튼, ui/`
- `/new-component 토스트 알림 — 상단 표시, 자동 소멸, 순수 컴포넌트`

---

## Step 1 — 컨텍스트 파일 읽기

생성 전에 반드시 아래 파일들을 읽는다:

1. `src/components/ui/button.tsx` — CVA 패턴 참고
2. `src/components/ui/sort-toggle.tsx` — 단순 props 기반 패턴 참고
3. `src/components/ui/hair-style-card.tsx` — 카드형 컴포넌트 패턴 참고
4. `.claude/commands/design-system.md` — 토큰 및 기존 컴포넌트 목록 확인

---

## Step 2 — 컴포넌트 파라미터 결정

`$ARGUMENTS`에서 추론한다. 모호하면 사용자에게 질문한다.

| 파라미터 | 추론 방법 |
|---------|---------|
| 컴포넌트명 | PascalCase, 예: `StatusBadge` |
| 파일명 | kebab-case, 예: `status-badge` |
| 배치 경로 | 재사용 가능한 원자적 UI → `src/components/ui/`, 특정 기능/도메인 전용 → `src/components/` |
| CVA 사용 여부 | 시각적 변형(variant)이 2개 이상 → CVA 사용, 단순 → props만 |
| 상태 여부 | 내부 상태 필요 여부 (useState 등) |

### 배치 기준

| 경로 | 기준 |
|------|------|
| `src/components/ui/` | 범용 원자 컴포넌트 (버튼, 카드, 토글, 뱃지 등) |
| `src/components/` | 도메인 전용 컴포넌트 (Header, BottomNav 등) |

---

## Step 3 — 컴포넌트 파일 생성

### 템플릿 A: CVA 기반 (변형이 있는 경우)

```tsx
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const componentVariants = cva(
  '/* 공통 기본 클래스 */',
  {
    variants: {
      variant: {
        default: '/* 기본 스타일 */',
        secondary: '/* 보조 스타일 */',
      },
      size: {
        sm: '/* 소 */',
        md: '/* 중 */',
        lg: '/* 대 */',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
)

type ComponentNameProps = React.ComponentProps<'div'> &
  VariantProps<typeof componentVariants> & {
    // 추가 props
  }

export function ComponentName({
  className,
  variant,
  size,
  ...props
}: ComponentNameProps) {
  return (
    <div
      className={cn(componentVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { componentVariants }
export type { ComponentNameProps }
```

### 템플릿 B: 단순 props 기반 (변형 없는 경우)

```tsx
import { cn } from '@/lib/utils'

type ComponentNameProps = {
  // props 정의
  className?: string
}

export function ComponentName({ className, ...props }: ComponentNameProps) {
  return (
    <div className={cn('/* 기본 클래스 */', className)}>
      {/* 콘텐츠 */}
    </div>
  )
}

export type { ComponentNameProps }
```

### 템플릿 C: 카드형 컴포넌트

```tsx
import { cn } from '@/lib/utils'

type ComponentNameProps = {
  // 데이터 props
  title: string
  // 이벤트 props
  onClick?: () => void
  className?: string
}

export function ComponentName({
  title,
  onClick,
  className,
}: ComponentNameProps) {
  return (
    <article
      className={cn(
        '/* 카드 기본 스타일 */',
        className,
      )}
    >
      {/* 콘텐츠 */}
    </article>
  )
}

export type { ComponentNameProps }
```

### 코딩 규칙

- raw hex 금지 — 모든 색상은 Tailwind 토큰 클래스
- 모든 UI 문자열은 한국어
- `type` 키워드 사용 (interface 아님)
- 사용하는 것만 import (미사용 import 없음)
- `className` prop은 항상 마지막, `cn()` 으로 병합
- 이미지에는 `draggable={false}` 추가
- 토글/선택 버튼에는 `aria-pressed` 추가
- 아이콘 버튼에는 `aria-label` 필수
- `export` 방식: named export (`export function` / `export { ... }`)
- 내부 상태가 없으면 순수 컴포넌트(props만)로 유지

---

## Step 4 — design-system.md 업데이트

`FE/.claude/commands/design-system.md`의 **"UI 컴포넌트"** 섹션에 새 항목을 추가한다.

추가 형식:

```md
### ComponentName (`src/components/ui/component-name.tsx`)

\```tsx
import { ComponentName } from '@/components/ui/component-name'

// 최소 사용 예시
<ComponentName prop="값" />

// variant 있는 경우
<ComponentName variant="secondary" size="sm">내용</ComponentName>
\```
```

---

## Step 5 — 검증 체크리스트

- [ ] `src/components/ui/{file-name}.tsx` 또는 `src/components/{file-name}.tsx` 생성 완료
- [ ] CVA 사용 여부가 변형 개수에 맞게 결정됨
- [ ] raw hex 없음
- [ ] 미사용 import 없음
- [ ] `className` + `cn()` 병합 포함
- [ ] 필요한 aria 속성 추가됨
- [ ] `design-system.md` 업데이트 완료
- [ ] `npm run build` 타입 에러 없음 확인 권고
