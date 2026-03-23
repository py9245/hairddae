# 헤어때 디자인 시스템 레퍼런스

헤어때 FE 프로젝트의 디자인 토큰, 컴포넌트, 패턴을 정리한 자기완결형 레퍼런스입니다.

---

## 프로젝트 스택

| 항목 | 버전/라이브러리 |
|------|----------------|
| 프레임워크 | React 19 |
| 스타일링 | Tailwind v4 (`@theme inline` 방식) |
| 라우터 | TanStack Router |
| 컴포넌트 변형 | CVA (class-variance-authority) |
| 아이콘 | lucide-react |
| UI 기반 | radix-ui (Slot, Dialog, Popover 등) |

> **규칙**: raw hex 절대 금지. 모든 색상은 Tailwind 토큰 클래스(`bg-primary-300`, `text-text-warm-500` 등) 사용.

---

## 레이아웃 프레임

```
app-frame-shell   ← 전체 화면, 좌우 중앙 정렬, safe-area 패딩 처리
  app-frame       ← 최대 너비 430px, 모바일 카드 프레임, overflow hidden
    app-frame-content  ← 100dvh, overflow hidden, pb safe-area
      [페이지]    ← app-frame-page (min-height 100%)
    BottomNav     ← absolute 포지션, 화면 하단 82px
```

### 클래스 설명

| 클래스 | 역할 |
|--------|------|
| `app-frame-shell` | 전체 뷰포트, safe-area inset 처리 |
| `app-frame` | 430px 모바일 프레임, `overflow: hidden` |
| `app-frame-content` | 100dvh 컨테이너, 스크롤 격리 |
| `app-frame-page` | 각 페이지 루트 요소 (`min-height: 100%`) |
| `app-frame-fill` | `min-height: 100%` (대체 옵션) |

---

## 표준 페이지 루트 패턴

### 1. 스크롤 보호 페이지 (바텀 내비 있음) — `main.tsx` 패턴

```tsx
<main className="app-frame-page h-full overflow-y-auto bg-neutral-500 pb-[108px] text-text-warm-500">
  <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
    <Header label="헤어때" labelClassName="text-primary-300 tracking-[-0.04em]" />
    {/* 콘텐츠 */}
  </div>
</main>
```

### 2. 서브페이지 (뒤로 가기 헤더, 헤더가 absolute → `pt-16` 필수)

```tsx
<main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
  <Header
    leftAction={<button onClick={() => navigate({ to: -1 })} aria-label="뒤로 가기"><ChevronLeft /></button>}
    centerContent={<h1 className="text-base font-semibold text-text-dark">페이지 제목</h1>}
  />
  <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-16">
    {/* 콘텐츠 */}
  </div>
</main>
```

### 3. 공개/인증 전 페이지 (바텀 내비 없음) — `login.tsx` 패턴

```tsx
<main className="app-frame-page flex flex-col items-center justify-center bg-bg-primary px-6 py-10">
  <div className="w-full max-w-md">
    {/* 콘텐츠 */}
  </div>
</main>
```

### 4. 모달 오버레이 배경색

모달 오버레이: `bg-black/50` (DialogOverlay 참고)

---

## 디자인 토큰 표

### 브랜드 핑크 (Primary)

| 토큰 | Tailwind 클래스 | 용도 |
|------|----------------|------|
| primary-50 | `bg-primary-50` | 가장 연한 핑크 배경 |
| primary-100 | `bg-primary-100` | 연한 핑크 |
| primary-150 | `bg-primary-150` | 핑크 배경 (중간 연함) |
| primary-200 | `bg-primary-200` / `text-primary-200` | 기본 버튼 배경 |
| primary-250 | `bg-primary-250` / `text-primary-250` | 바텀 내비 활성 아이콘 |
| primary-300 | `bg-primary-300` / `text-primary-300` | 메인 브랜드 컬러, 로고 텍스트, 로그인 버튼 |
| primary-400 | `bg-primary-400` | |
| primary-500 | `bg-primary-500` | |
| primary-hover | `bg-primary-hover` | 버튼 hover |
| primary-disabled | `bg-primary-disabled` | 버튼 disabled |
| primary-light | `bg-primary-light` | 연한 핑크 강조 배경 |

### 배경 / 뉴트럴

| 토큰 | Tailwind 클래스 | 용도 |
|------|----------------|------|
| bg-primary | `bg-bg-primary` | 앱 기본 배경 (`#f5f5f5`) |
| neutral-50 | `bg-neutral-50` | 가장 밝은 배경 |
| neutral-100 | `bg-neutral-100` | 밝은 배경 |
| neutral-200 | `bg-neutral-200` | 카테고리 더보기 버튼 배경 |
| neutral-300 | `bg-neutral-300` | 로그아웃 버튼 배경 |
| neutral-500 | `bg-neutral-500` | 메인 페이지 스크롤 배경 |
| nav-inactive | `text-nav-inactive` / `border-nav-inactive` | 바텀 내비 비활성 색상 |

### 텍스트

| 토큰 | Tailwind 클래스 | 용도 |
|------|----------------|------|
| text-dark | `text-text-dark` | 가장 짙은 본문 텍스트 |
| text-warm-100 | `text-text-warm-100` | 따뜻한 회색 (연함) |
| text-warm-200 | `text-text-warm-200` | |
| text-warm-300 | `text-text-warm-300` | |
| text-warm-400 | `text-text-warm-400` | |
| text-warm-500 | `text-text-warm-500` | 메인 페이지 기본 텍스트 |
| text-warm-600 | `text-text-warm-600` | 헤딩 텍스트 (가장 짙은 warm) |
| labels-primary | `text-labels-primary` | 검정 레이블 |
| labels-secondary | `text-labels-secondary` | 보조 레이블 |

### 그림자

| CSS 변수 | 사용법 | 용도 |
|---------|--------|------|
| `--shadow-pink-sm` | `shadow-[0_6px_16px_rgba(255,143,163,0.34)]` | 핑크 소 그림자 |
| `--shadow-pink-md` | `shadow-[0_8px_18px_rgba(255,154,173,0.32)]` | 핑크 중 그림자 |
| `--shadow-pink-card` | `shadow-[0_4px_12px_rgba(227,194,194,0.32)]` | 카드 핑크 그림자 |
| `--shadow-dark-sm` | `shadow-[0_4px_12px_rgba(15,23,42,0.15)]` | 어두운 소 그림자 |
| `--shadow-dark-md` | `shadow-[0_4px_12px_rgba(15,23,42,0.28)]` | 어두운 중 그림자 |

### 그라디언트

```css
/* primary-gradient: 왼쪽(#ffa7a6) → 오른쪽(#ea7589) */
/* Tailwind arbitrary: */
bg-[linear-gradient(90deg,theme(colors.primary-250)_0%,theme(colors.primary-300)_100%)]
```

### 기타

| 토큰 | 클래스 | 용도 |
|------|--------|------|
| error | `text-error` | 에러 텍스트 |
| indicator-active | `bg-indicator-active` | 인디케이터 활성 |
| indicator-inactive | `bg-indicator-inactive` | 인디케이터 비활성 |

---

## 타이포그래피

| 패턴 | 클래스 |
|------|--------|
| 본문 기본 | `font-sans` (Pretendard) |
| 디스플레이/로고 | `font-display` (Hakgyoansim Byeolbichhaneul) |
| 메인 헤딩 | `text-24 font-extrabold tracking-[-0.05em] text-text-warm-600` |
| 로고 텍스트 | `font-display text-[32px] font-bold leading-none text-primary-300 tracking-[-0.04em]` |
| 서브페이지 타이틀 | `text-base font-semibold text-text-dark` |
| 소제목 | `text-sm font-medium` |

---

## UI 컴포넌트

### Button (`src/components/ui/button.tsx`)

```tsx
import { Button } from '@/components/ui/button'

// variant / size 조합
<Button variant="splash" size="splash">시작하기</Button>
<Button variant="login" size="full">로그인</Button>
<Button variant="logout" size="full">로그아웃</Button>
<Button variant="outline" size="sm">취소</Button>
<Button variant="destructive">삭제</Button>
<Button variant="ghost" size="icon"><Icon /></Button>
```

#### 주요 variant

| variant | 외관 | 용도 |
|---------|------|------|
| `splash` | `bg-primary-300`, disabled 지원 | 스플래시 CTA |
| `login` | `bg-primary-300`, disabled 지원 | 로그인/회원가입 |
| `logout` | `bg-neutral-300` | 로그아웃 |
| `outline` | 테두리, 배경 transparent | 보조 액션 |
| `destructive` | 빨간 배경 | 삭제/위험 |
| `ghost` | 배경 없음 | 아이콘 버튼 |
| `camera-back` / `camera-setting` | 흰색 반투명 | 카메라 UI |
| `hair-download` | 흰 배경, 테두리 | 헤어 다운로드 |

#### 주요 size

| size | 설명 |
|------|------|
| `full` | `h-[52px] w-full rounded-xl` — 전체 너비 버튼 |
| `splash` | `h-14 w-full rounded-[8px]` — 스플래시 CTA |
| `icon` | `size-9` — 정사각형 아이콘 버튼 |
| `icon-sm` | `size-8` |
| `icon-lg` | `size-10` |
| `sm` / `lg` / `default` | 표준 크기 |

---

### Header (`src/components/header.tsx`)

두 가지 모드:

#### 모드 1: 로고 모드 (`label` prop 제공)

```tsx
import { Header } from '@/components/header'

// 로고 이미지(size-12) + 텍스트
<Header
  label="헤어때"
  labelClassName="text-primary-300 tracking-[-0.04em]"
  className="px-0 pb-3 pt-2"
/>
```

#### 모드 2: 3컬럼 내비 모드 (`label` prop 없음, absolute 포지션)

```tsx
// absolute inset-x-0 top-0 z-20 → 페이지 콘텐츠에 pt-16 필요
// 뒤로 가기: useRouter().history.back() 사용 (navigate({ to: -1 })은 타입 에러)
<Header
  leftAction={
    <button type="button" onClick={() => router.history.back()} aria-label="뒤로 가기">
      <ChevronLeft className="size-6" />
    </button>
  }
  centerContent={<h1 className="text-base font-semibold text-text-dark">제목</h1>}
  rightAction={<button type="button" aria-label="더 보기"><MoreVertical className="size-5" /></button>}
/>
```

---

### Dialog (`src/components/ui/dialog.tsx`)

```tsx
import {
  Dialog, DialogTrigger, DialogContent,
  DialogHeader, DialogTitle, DialogDescription, DialogFooter
} from '@/components/ui/dialog'

<Dialog>
  <DialogTrigger asChild>
    <Button>열기</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>제목</DialogTitle>
      <DialogDescription>설명</DialogDescription>
    </DialogHeader>
    {/* 콘텐츠 */}
    <DialogFooter>
      <Button variant="outline">취소</Button>
      <Button variant="splash">확인</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

오버레이 배경: `bg-black/50` (자동 적용)

---

### Field (`src/components/ui/field.tsx`)

```tsx
import { Field, FieldLabel, FieldError, FieldGroup } from '@/components/ui/field'

<FieldGroup>
  <Field>
    <FieldLabel htmlFor="name">이름</FieldLabel>
    <input id="name" className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface px-4 ..." />
    <FieldError errors={[{ message: '필수 항목입니다' }]} />
  </Field>
</FieldGroup>
```

---

### SortToggle (`src/components/ui/sort-toggle.tsx`)

```tsx
import { SortToggle } from '@/components/ui/sort-toggle'

const options = [
  { value: 'popular', label: '인기순' },
  { value: 'latest', label: '최신순' },
] as const

<SortToggle options={options} value={sortValue} onChange={setSortValue} />
```

---

### CategoryCard (`src/components/ui/category-card.tsx`)

```tsx
import { CategoryCard } from '@/components/ui/category-card'

<button type="button" onClick={...}>
  <CategoryCard label="단발" imageSrc="/hiar-style/style-01-image.png" />
</button>
```

---

### HairStyleCard (`src/components/ui/hair-style-card.tsx`)

```tsx
import { HairStyleCard } from '@/components/ui/hair-style-card'

<HairStyleCard
  imageSrc="/hiar-style/style-01-image.png"
  imageAlt="헤어스타일 예시"
  title="트렌디한\n쇼트 컷"
  subtitle="숏컷"
  liked={liked}
  className="w-full"
  onLikeToggle={() => setLiked(prev => !prev)}
  onApply={() => {}}
/>
```

---

### BottomSheet (`src/components/ui/bottom-sheet.tsx`)

```tsx
import { BottomSheet } from '@/components/ui/bottom-sheet'

<BottomSheet
  isOpen={isOpen}
  onClose={() => setIsOpen(false)}
  title="시트 제목"
>
  {/* 시트 내부 콘텐츠 */}
</BottomSheet>
```

---

### CategoryBottomSheet (`src/components/ui/category-bottom-sheet.tsx`)

```tsx
import { CategoryBottomSheet } from '@/components/ui/category-bottom-sheet'

<CategoryBottomSheet
  open={isCategorySheetOpen}
  onClose={() => setIsCategorySheetOpen(false)}
  categories={categories}
  selectedCategory={selectedCategoryId}
  onSelect={(categoryID) => {
    // 선택 처리
    setIsCategorySheetOpen(false)
  }}
/>
```

---

### StyleAdsCard (`src/components/ui/style-ads-card.tsx`)

```tsx
import { StyleAdsCard } from '@/components/ui/style-ads-card'

<StyleAdsCard
  hairImgpath="/hiar-style/style-02-image.png"
  hairSlug="봄의 시작을 알리는 여신머리"
  hairName="레이어드컷"
  liked={heroLiked}
  className="w-full"
  onLikeToggle={() => setHeroLiked(prev => !prev)}
  onApply={() => {}}
/>
```

---

## Input 표준 패턴

```tsx
// 기본 텍스트 입력
<input
  id="fieldId"
  type="text"
  placeholder="입력하세요"
  className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface px-4 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
/>

// 비밀번호 (토글 버튼 포함)
<div className="relative">
  <input
    id="password"
    type={showPassword ? 'text' : 'password'}
    className="h-12 w-full rounded-2xl border border-gray-200 bg-input-surface px-4 pr-12 text-base text-slate-700 placeholder:text-sm placeholder:text-gray-400 outline-none focus:border-primary-200"
  />
  <button
    type="button"
    onClick={() => setShowPassword(prev => !prev)}
    className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"
    aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'}
  >
    {showPassword ? <Eye className="h-5 w-5" /> : <EyeClosed className="h-5 w-5" />}
  </button>
</div>
```

---

## 아이콘 사용법 (lucide-react)

```tsx
import { ChevronLeft, ChevronDown, Camera, House, UserRound, Eye, EyeClosed } from 'lucide-react'

// 기본 크기
<ChevronLeft className="size-6" strokeWidth={1.5} />

// 바텀 내비 아이콘
<Icon className="size-[28px]" strokeWidth={1.5} />

// 이미지에 draggable 방지
<img src="..." draggable={false} alt="설명" />
```

---

## 접근성 관례

```tsx
// 현재 페이지 표시
<Link aria-current="page" to="/main">홈</Link>

// 토글 버튼
<button aria-pressed={isActive} type="button">정렬</button>

// 에러 메시지
<div role="alert" className="text-sm text-destructive">오류 메시지</div>

// 스크린 리더 전용 텍스트
<span className="sr-only">닫기</span>

// 이미지 드래그 방지
<img draggable={false} src="..." alt="..." />

// 뒤로 가기 버튼
<button type="button" aria-label="뒤로 가기">
  <ChevronLeft className="size-6" />
</button>
```

---

## 자주 쓰는 레이아웃 패턴

```tsx
// 2열 그리드 카드
<div className="grid grid-cols-2 gap-x-3 gap-y-4">
  {items.map(item => <Card key={item.id} />)}
</div>

// 가로 스크롤 섹션
<div className="min-w-0 flex-1 overflow-x-auto pb-1">
  <div className="flex min-w-max items-start gap-3">
    {items.map(item => <Item key={item.id} />)}
  </div>
</div>

// 헤딩 + 정렬 토글 행
<div className="flex items-center justify-between gap-3">
  <h2 className="text-24 leading-none font-extrabold tracking-[-0.05em] text-text-warm-600">
    섹션 제목
  </h2>
  <SortToggle options={options} value={sort} onChange={setSort} />
</div>
```
