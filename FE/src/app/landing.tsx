import { Link } from '@tanstack/react-router'
import { Camera, Check, Heart, Layers, Share2, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

// ─── Cursor ───────────────────────────────────────────────────────────────────

function CustomCursor() {
  const dotRef = useRef<HTMLDivElement>(null)
  const ringRef = useRef<HTMLDivElement>(null)
  const pos = useRef({ x: -200, y: -200 })
  const ring = useRef({ x: -200, y: -200 })
  const isPointer = useRef(false)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      pos.current = { x: e.clientX, y: e.clientY }
      const target = e.target as Element | null
      isPointer.current =
        target instanceof Element &&
        window.getComputedStyle(target).cursor === 'pointer'

      // dot follows instantly
      if (dotRef.current) {
        dotRef.current.style.transform = `translate(${e.clientX - 4}px, ${e.clientY - 4}px)`
      }
    }

    const animate = () => {
      ring.current.x += (pos.current.x - ring.current.x) * 0.13
      ring.current.y += (pos.current.y - ring.current.y) * 0.13

      if (ringRef.current) {
        const size = isPointer.current ? 44 : 32
        ringRef.current.style.transform = `translate(${ring.current.x - size / 2}px, ${ring.current.y - size / 2}px)`
        ringRef.current.style.width = `${size}px`
        ringRef.current.style.height = `${size}px`
        ringRef.current.style.opacity = isPointer.current ? '1' : '0.65'
        ringRef.current.style.background = isPointer.current
          ? 'rgba(249,168,212,0.15)'
          : 'transparent'
      }

      rafRef.current = requestAnimationFrame(animate)
    }

    window.addEventListener('mousemove', onMove)
    rafRef.current = requestAnimationFrame(animate)
    return () => {
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(rafRef.current)
    }
  }, [])

  return (
    <>
      {/* dot */}
      <div
        ref={dotRef}
        className="pointer-events-none fixed z-[9999]"
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: 'var(--color-primary-300)',
          boxShadow: '0 0 6px 2px rgba(249,168,212,0.6)',
          willChange: 'transform',
        }}
      />
      {/* ring */}
      <div
        ref={ringRef}
        className="pointer-events-none fixed z-[9998]"
        style={{
          borderRadius: '50%',
          border: '1.5px solid var(--color-primary-300)',
          transition:
            'width 0.25s ease, height 0.25s ease, opacity 0.2s ease, background 0.2s ease',
          willChange: 'transform',
        }}
      />
    </>
  )
}

// ─── Hooks ───────────────────────────────────────────────────────────────────

function useReveal(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { threshold },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])
  return { ref, visible }
}

function useCounter(target: number, duration = 1800, active = false) {
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (!active) return
    let startTime: number | null = null
    const easeOut = (t: number) => 1 - (1 - t) ** 3
    const step = (ts: number) => {
      if (!startTime) startTime = ts
      const progress = Math.min((ts - startTime) / duration, 1)
      setCount(Math.floor(easeOut(progress) * target))
      if (progress < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }, [target, duration, active])
  return count
}

function useScrolled(offset = 10) {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const container = document.getElementById('landing-scroll')
    if (!container) return
    const onScroll = () => setScrolled(container.scrollTop > offset)
    container.addEventListener('scroll', onScroll, { passive: true })
    return () => container.removeEventListener('scroll', onScroll)
  }, [offset])
  return scrolled
}

function useScrollProgress() {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    const container = document.getElementById('landing-scroll')
    if (!container) return
    const update = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      setProgress(scrollTop / (scrollHeight - clientHeight) || 0)
    }
    container.addEventListener('scroll', update, { passive: true })
    return () => container.removeEventListener('scroll', update)
  }, [])
  return progress
}

function useOnboardingStep(totalSteps: number) {
  const outerRef = useRef<HTMLDivElement>(null)
  const [step, setStep] = useState(0)
  const [localProgress, setLocalProgress] = useState(0)

  useEffect(() => {
    const container = document.getElementById('landing-scroll')
    if (!container) return
    const update = () => {
      const el = outerRef.current
      if (!el) return
      const { top, height } = el.getBoundingClientRect()
      const viewH = container.clientHeight
      const scrolled = viewH - top
      const total = height - viewH
      const p = Math.max(0, Math.min(1, scrolled / total))
      setLocalProgress(p)
      setStep(Math.min(totalSteps - 1, Math.floor(p * totalSteps)))
    }
    container.addEventListener('scroll', update, { passive: true })
    update()
    return () => container.removeEventListener('scroll', update)
  }, [totalSteps])

  return { outerRef, step, localProgress }
}

// ─── Data ─────────────────────────────────────────────────────────────────────

const HAIR_WORDS = [
  '레이어드컷',
  '베이비컷',
  '울프컷',
  '애쉬컷',
  '히피펌',
  '내추럴웨이브',
]

type FeatureTab = {
  id: string
  icon: typeof Camera
  label: string
  badge: string
  title: string
  description: string
  points: string[]
}

const FEATURES: FeatureTab[] = [
  {
    id: 'camera',
    icon: Camera,
    label: 'AI 카메라',
    badge: '실시간 AR',
    title: 'AI 가상 헤어 체험',
    description:
      '카메라를 켜는 순간, AI가 얼굴을 자동 인식하고 원하는 헤어스타일을 실시간으로 입혀드려요. 미용실 가기 전에 먼저 체험해보세요.',
    points: ['얼굴형 자동 인식', '실시간 AR 렌더링', '결과 사진 저장'],
  },
  {
    id: 'recommend',
    icon: Sparkles,
    label: 'AI 추천',
    badge: 'AI 분석',
    title: '나에게 딱 맞는 헤어 추천',
    description:
      '얼굴형, 취향, 최신 트렌드를 종합 분석한 AI가 지금 가장 어울리는 헤어스타일을 골라드려요.',
    points: [
      '얼굴형 분석 기반 추천',
      '트렌드 반영 업데이트',
      '인기순·최신순 정렬',
    ],
  },
  {
    id: 'explore',
    icon: Layers,
    label: '카테고리 탐색',
    badge: '트렌드',
    title: '수백 가지 스타일을 한눈에',
    description:
      '숏컷부터 장발까지, 클래식부터 최신 트렌드까지 다양한 카테고리에서 원하는 스타일을 자유롭게 탐색하세요.',
    points: ['카테고리별 분류', '좋아요로 즐겨찾기', '헤어 이름·특징 안내'],
  },
]

type OnboardingStep = {
  step: string
  title: string
  description: string
  color: string
  screen: 'signup' | 'explore' | 'camera' | 'result'
}

const ONBOARDING: OnboardingStep[] = [
  {
    step: '01',
    title: '간편 회원가입',
    description:
      '이메일 하나로 30초 만에 가입 완료. 복잡한 절차 없이 바로 시작할 수 있어요.',
    color: 'from-pink-50 to-rose-100',
    screen: 'signup',
  },
  {
    step: '02',
    title: '스타일 탐색',
    description:
      '숏컷·미디엄·롱까지 수백 가지 스타일을 카테고리별로 자유롭게 둘러보세요.',
    color: 'from-fuchsia-50 to-pink-100',
    screen: 'explore',
  },
  {
    step: '03',
    title: 'AI 카메라 체험',
    description:
      '카메라를 켜면 AI가 실시간으로 내 얼굴에 선택한 스타일을 입혀드려요.',
    color: 'from-rose-50 to-pink-100',
    screen: 'camera',
  },
  {
    step: '04',
    title: '결과 저장·공유',
    description:
      '마음에 든 스타일을 저장하고, 친구들에게 공유해 의견을 들어보세요.',
    color: 'from-pink-50 to-fuchsia-100',
    screen: 'result',
  },
]

type TeamMember = {
  name: string
  roles: string[]
  github: string
}

const TEAM: TeamMember[] = [
  {
    name: '심미진',
    roles: ['Front-end', 'PM'],
    github: 'https://github.com/azure-553',
  },
  { name: '김영훈', roles: ['AI'], github: 'https://github.com/younghoon129' },
  {
    name: '신건하',
    roles: ['Front-end'],
    github: 'https://github.com/taek-99',
  },
  {
    name: '박유신',
    roles: ['Back-end', 'AI'],
    github: 'https://github.com/py9245',
  },
  { name: '김두진', roles: ['Back-end'], github: 'https://github.com/duuujin' },
]

// ─── Sub Components ───────────────────────────────────────────────────────────

function RevealBox({
  children,
  delay = 0,
  className = '',
  from = 'bottom',
}: {
  children: React.ReactNode
  delay?: number
  className?: string
  from?: 'bottom' | 'left' | 'right'
}) {
  const { ref, visible } = useReveal()
  const hiddenTransform =
    from === 'left'
      ? 'translateX(-40px)'
      : from === 'right'
        ? 'translateX(40px)'
        : 'translateY(32px)'
  return (
    <div
      ref={ref}
      className={className}
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? 'translate(0,0)' : hiddenTransform,
        transition: `opacity 0.65s ease ${delay}ms, transform 0.65s ease ${delay}ms`,
      }}
    >
      {children}
    </div>
  )
}

function TiltCard({
  children,
  className = '',
  strength = 10,
}: {
  children: React.ReactNode
  className?: string
  strength?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [style, setStyle] = useState<React.CSSProperties>({
    transition: 'transform 0.5s ease',
  })

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const handleMouseMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      const x = (e.clientX - rect.left - rect.width / 2) / (rect.width / 2)
      const y = (e.clientY - rect.top - rect.height / 2) / (rect.height / 2)
      setStyle({
        transform: `perspective(900px) rotateY(${x * strength}deg) rotateX(${-y * strength}deg) translateZ(6px)`,
        transition: 'transform 0.1s ease',
      })
    }

    const handleMouseLeave = () => {
      setStyle({
        transform:
          'perspective(900px) rotateY(0deg) rotateX(0deg) translateZ(0)',
        transition: 'transform 0.5s ease',
      })
    }

    el.addEventListener('mousemove', handleMouseMove)
    el.addEventListener('mouseleave', handleMouseLeave)

    return () => {
      el.removeEventListener('mousemove', handleMouseMove)
      el.removeEventListener('mouseleave', handleMouseLeave)
    }
  }, [strength])

  return (
    <div ref={ref} className={className} style={style}>
      {children}
    </div>
  )
}

function ScrollProgressBar() {
  const progress = useScrollProgress()
  return (
    <div className="pointer-events-none absolute left-0 right-0 top-0 z-[60] h-[3px]">
      <div
        className="h-full bg-primary-300"
        style={{
          width: `${progress * 100}%`,
          transition: 'width 0.05s linear',
        }}
      />
    </div>
  )
}

function StatsSection() {
  const { ref, visible } = useReveal()
  const styles = useCounter(500, 1600, visible)
  const satisfaction = useCounter(98, 1400, visible)
  const users = useCounter(50, 1800, visible)

  return (
    <div ref={ref} className="border-y border-neutral-100 bg-white px-6 py-12">
      <div className="mx-auto grid max-w-4xl grid-cols-3 gap-4">
        {[
          { value: styles, suffix: '+', unit: '가지', label: '헤어스타일' },
          {
            value: satisfaction,
            suffix: '%',
            unit: '',
            label: '사용자 만족도',
          },
          { value: users, suffix: '만+', unit: '', label: '누적 체험 수' },
        ].map(({ value, suffix, unit, label }) => (
          <div key={label} className="text-center">
            <p className="text-3xl font-extrabold tracking-[-0.04em] text-primary-300 md:text-5xl">
              {value}
              {suffix}
              {unit && <span className="text-xl md:text-2xl">{unit}</span>}
            </p>
            <p className="mt-1 text-xs font-medium text-text-warm-300 md:text-sm">
              {label}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}

function FeatureTabs() {
  const [active, setActive] = useState(0)
  const [animating, setAnimating] = useState(false)

  function handleSelect(index: number) {
    if (index === active) return
    setAnimating(true)
    setTimeout(() => {
      setActive(index)
      setAnimating(false)
    }, 200)
  }

  const current = FEATURES[active]

  return (
    <section className="bg-white px-6 py-20 md:py-28">
      <div className="mx-auto max-w-6xl">
        <RevealBox className="text-center">
          <h2 className="text-3xl font-extrabold tracking-[-0.04em] text-text-dark md:text-4xl">
            헤어때만의 핵심 기능
          </h2>
          <p className="mt-3 text-text-warm-300 md:text-lg">
            AI 기술로 더 스마트하게 헤어스타일을 선택하세요
          </p>
        </RevealBox>

        <RevealBox delay={150} className="mt-14">
          <div className="flex gap-3 overflow-x-auto pb-1">
            {FEATURES.map((f, i) => {
              const Icon = f.icon
              const isActive = i === active
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => handleSelect(i)}
                  className="flex shrink-0 items-center gap-2 rounded-full px-5 py-2.5 text-sm font-semibold transition-all duration-300"
                  style={{
                    background: isActive
                      ? 'var(--color-primary-300)'
                      : 'var(--color-neutral-100)',
                    color: isActive ? '#fff' : 'var(--color-text-warm-300)',
                    boxShadow: isActive ? 'var(--shadow-pink-sm)' : 'none',
                  }}
                  aria-pressed={isActive}
                >
                  <Icon className="size-4" strokeWidth={1.5} />
                  {f.label}
                </button>
              )
            })}
          </div>

          <TiltCard
            strength={6}
            className="mt-6 overflow-hidden rounded-3xl border border-neutral-100 bg-neutral-50"
          >
            <div
              className="grid md:grid-cols-2"
              style={{
                opacity: animating ? 0 : 1,
                transform: animating ? 'translateX(12px)' : 'translateX(0)',
                transition: 'opacity 0.2s ease, transform 0.2s ease',
              }}
            >
              <div className="flex flex-col justify-center p-8 md:p-12">
                <span className="w-fit rounded-full bg-primary-100 px-3 py-1 text-xs font-semibold text-primary-300">
                  {current.badge}
                </span>
                <h3 className="mt-4 text-2xl font-extrabold tracking-[-0.03em] text-text-dark md:text-3xl">
                  {current.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-text-warm-300 md:text-base">
                  {current.description}
                </p>
                <ul className="mt-6 space-y-2">
                  {current.points.map((pt) => (
                    <li
                      key={pt}
                      className="flex items-center gap-2 text-sm text-text-warm-500"
                    >
                      <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-primary-100">
                        <Check
                          className="size-3 text-primary-300"
                          strokeWidth={2.5}
                        />
                      </span>
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 p-10 md:p-16">
                <div className="flex size-32 items-center justify-center rounded-3xl bg-white shadow-[var(--shadow-pink-card)] md:size-44">
                  {(() => {
                    const Icon = current.icon
                    return (
                      <Icon
                        className="size-16 text-primary-300 md:size-24"
                        strokeWidth={1}
                      />
                    )
                  })()}
                </div>
              </div>
            </div>
          </TiltCard>
        </RevealBox>
      </div>
    </section>
  )
}

// ─── Phone Mockup Screens ─────────────────────────────────────────────────────

function PhoneScreen({ screen }: { screen: OnboardingStep['screen'] }) {
  if (screen === 'signup') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 bg-white px-5 pb-6 pt-10">
        <div className="flex size-12 items-center justify-center rounded-full bg-primary-300 text-lg font-bold text-white">
          헤
        </div>
        <p className="text-center text-[11px] font-bold text-text-dark">
          헤어때에 오신 것을 환영해요
        </p>
        <p className="text-[9px] text-text-warm-300">
          이메일로 빠르게 시작하세요
        </p>
        <div className="mt-2 w-full space-y-2">
          <div className="flex h-8 w-full items-center rounded-xl bg-neutral-100 px-3">
            <div className="h-1.5 w-20 rounded-full bg-neutral-300" />
          </div>
          <div className="flex h-8 w-full items-center rounded-xl bg-neutral-100 px-3">
            <div className="h-1.5 w-16 rounded-full bg-neutral-300" />
          </div>
        </div>
        <div className="mt-1 flex h-9 w-full items-center justify-center rounded-xl bg-primary-300">
          <div className="h-1.5 w-16 rounded-full bg-white/70" />
        </div>
        <div className="flex items-center gap-2">
          <div className="h-px w-12 bg-neutral-200" />
          <span className="text-[8px] text-neutral-400">또는</span>
          <div className="h-px w-12 bg-neutral-200" />
        </div>
        <div className="flex h-8 w-full items-center justify-center gap-1.5 rounded-xl border border-neutral-200">
          <div className="size-3 rounded-full bg-neutral-300" />
          <div className="h-1.5 w-14 rounded-full bg-neutral-300" />
        </div>
      </div>
    )
  }

  if (screen === 'explore') {
    return (
      <div className="flex h-full flex-col bg-white">
        <div className="flex items-center gap-2 px-3 pb-2 pt-8">
          <div className="h-7 flex-1 rounded-full bg-neutral-100" />
          <div className="size-7 rounded-full bg-neutral-100" />
        </div>
        <div className="flex gap-1.5 overflow-x-hidden px-3 pb-2">
          {[
            { id: 'active', className: 'bg-primary-300' },
            { id: 'inactive-1', className: 'bg-neutral-200' },
            { id: 'inactive-2', className: 'bg-neutral-200' },
            { id: 'inactive-3', className: 'bg-neutral-200' },
          ].map(({ id, className }) => (
            <div
              key={id}
              className={`h-5 shrink-0 rounded-full px-3 text-[7px] ${className}`}
            />
          ))}
        </div>
        <div className="grid flex-1 grid-cols-2 gap-2 overflow-hidden px-3 pb-3">
          {[
            'bg-gradient-to-br from-pink-100 to-rose-200',
            'bg-gradient-to-br from-fuchsia-100 to-pink-200',
            'bg-gradient-to-br from-rose-100 to-pink-150',
            'bg-gradient-to-br from-pink-100 to-fuchsia-150',
          ].map((bg) => (
            <div
              key={bg}
              className={`relative overflow-hidden rounded-xl ${bg}`}
            >
              <div className="absolute bottom-1.5 left-1.5 right-1.5">
                <div className="h-1.5 w-10 rounded-full bg-white/70" />
                <div className="mt-0.5 h-1 w-7 rounded-full bg-white/50" />
              </div>
              <div className="absolute right-1.5 top-1.5 size-4 rounded-full bg-white/50 flex items-center justify-center">
                <Heart
                  className="size-2 text-primary-300"
                  fill="currentColor"
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (screen === 'camera') {
    return (
      <div className="relative flex h-full w-full items-center justify-center overflow-hidden bg-gradient-to-b from-neutral-800 to-neutral-900">
        {/* grid overlay */}
        <div
          className="pointer-events-none absolute inset-0 opacity-20"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        />
        {/* face + hair */}
        <div className="relative flex flex-col items-center">
          {/* hair */}
          <div
            className="relative z-10"
            style={{
              width: 80,
              height: 44,
              borderRadius: '50% 50% 0 0',
              background: 'linear-gradient(135deg, #f9a8d4, #ec4899)',
              marginBottom: -8,
              opacity: 0.85,
            }}
          />
          {/* face */}
          <div
            style={{
              width: 68,
              height: 80,
              borderRadius: '50%',
              background: 'linear-gradient(160deg, #fde68a, #fcd34d)',
              position: 'relative',
              zIndex: 5,
            }}
          >
            <div className="absolute left-1/2 top-[35%] flex -translate-x-1/2 gap-4">
              <div className="size-2 rounded-full bg-neutral-700/60" />
              <div className="size-2 rounded-full bg-neutral-700/60" />
            </div>
            <div className="absolute bottom-[22%] left-1/2 h-1.5 w-6 -translate-x-1/2 rounded-full bg-rose-300/60" />
          </div>
        </div>
        {/* corner brackets */}
        <div className="pointer-events-none absolute inset-6">
          <div className="absolute left-0 top-0 h-5 w-5 rounded-tl-lg border-l-2 border-t-2 border-white/60" />
          <div className="absolute right-0 top-0 h-5 w-5 rounded-tr-lg border-r-2 border-t-2 border-white/60" />
          <div className="absolute bottom-0 left-0 h-5 w-5 rounded-bl-lg border-b-2 border-l-2 border-white/60" />
          <div className="absolute bottom-0 right-0 h-5 w-5 rounded-br-lg border-b-2 border-r-2 border-white/60" />
        </div>
        {/* AR label */}
        <div className="absolute left-1/2 top-8 -translate-x-1/2 rounded-full bg-primary-300/80 px-2.5 py-0.5 text-[8px] font-bold text-white">
          AI 실시간 적용 중
        </div>
        {/* shutter */}
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 size-10 rounded-full border-4 border-white/80 bg-white/20" />
      </div>
    )
  }

  // result
  return (
    <div className="flex h-full flex-col bg-white">
      <div className="relative flex-1 overflow-hidden bg-gradient-to-b from-primary-50 to-primary-100">
        <div className="flex h-full items-center justify-center">
          <div className="relative flex flex-col items-center">
            <div
              style={{
                width: 72,
                height: 40,
                borderRadius: '50% 50% 0 0',
                background: 'linear-gradient(135deg, #f9a8d4, #ec4899)',
                marginBottom: -6,
              }}
            />
            <div
              style={{
                width: 60,
                height: 72,
                borderRadius: '50%',
                background: 'linear-gradient(160deg, #fde68a, #fcd34d)',
              }}
            />
          </div>
        </div>
        <div className="absolute right-2.5 top-3 rounded-full bg-white px-2 py-0.5 shadow-sm">
          <span className="text-[7px] font-bold text-primary-300">
            ✨ AI 분석 완료
          </span>
        </div>
      </div>
      <div className="space-y-2 p-3">
        <div className="flex h-1.5 w-24 rounded-full bg-neutral-200" />
        <div className="flex h-1 w-16 rounded-full bg-neutral-100" />
        <div className="mt-2 flex gap-2">
          <div className="flex h-9 flex-1 items-center justify-center rounded-xl bg-primary-300">
            <div className="h-1.5 w-14 rounded-full bg-white/70" />
          </div>
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary-100">
            <Heart className="size-3.5 text-primary-300" />
          </div>
          <div className="flex size-9 items-center justify-center rounded-xl bg-neutral-100">
            <Share2 className="size-3.5 text-neutral-400" />
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Onboarding Section ───────────────────────────────────────────────────────

function OnboardingSection() {
  const { outerRef, step } = useOnboardingStep(ONBOARDING.length)
  const current = ONBOARDING[step]

  return (
    <section
      ref={outerRef}
      className="relative"
      style={{ height: `${ONBOARDING.length * 100}vh` }}
    >
      <div className="sticky top-0 flex h-screen items-center overflow-hidden bg-white px-6">
        {/* bg gradient follows step */}
        <div
          className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${current.color} opacity-30 transition-all duration-700`}
        />

        <div className="relative mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 md:grid-cols-2">
          {/* 텍스트 영역 */}
          <div className="order-2 md:order-1">
            {/* 스텝 도트 */}
            <div className="mb-8 flex gap-2">
              {ONBOARDING.map((item, i) => (
                <div
                  key={item.step}
                  className="h-1.5 rounded-full transition-all duration-500"
                  style={{
                    width: i === step ? 28 : 8,
                    background:
                      i === step
                        ? 'var(--color-primary-300)'
                        : i < step
                          ? 'var(--color-primary-200)'
                          : 'var(--color-neutral-200)',
                  }}
                />
              ))}
            </div>

            <div
              key={step}
              style={{ animation: 'onboardFadeIn 0.5s ease both' }}
            >
              <span className="inline-block rounded-full bg-primary-100 px-3 py-1 text-xs font-bold text-primary-300">
                STEP {current.step}
              </span>
              <h2 className="mt-4 text-3xl font-extrabold tracking-[-0.04em] text-text-dark md:text-4xl lg:text-5xl">
                {current.title}
              </h2>
              <p className="mt-4 max-w-md text-base leading-relaxed text-text-warm-300 md:text-lg">
                {current.description}
              </p>
            </div>

            {/* 스텝 목록 */}
            <div className="mt-10 space-y-3">
              {ONBOARDING.map((s, i) => (
                <div
                  key={s.step}
                  className="flex items-center gap-3 transition-all duration-300"
                  style={{ opacity: i === step ? 1 : 0.35 }}
                >
                  <div
                    className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold transition-all duration-300"
                    style={{
                      background:
                        i === step
                          ? 'var(--color-primary-300)'
                          : 'var(--color-neutral-100)',
                      color: i === step ? '#fff' : 'var(--color-text-warm-300)',
                    }}
                  >
                    {i < step ? '✓' : s.step}
                  </div>
                  <span
                    className="text-sm font-semibold transition-colors duration-300"
                    style={{
                      color:
                        i === step
                          ? 'var(--color-text-dark)'
                          : 'var(--color-text-warm-300)',
                    }}
                  >
                    {s.title}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 폰 목업 */}
          <div className="order-1 flex justify-center md:order-2">
            <div
              className="relative transition-all duration-700"
              style={{
                transform: `translateY(${step % 2 === 0 ? '-8px' : '8px'})`,
              }}
            >
              {/* 배경 blob */}
              <div
                className="absolute -inset-8 rounded-full opacity-40 blur-3xl transition-all duration-700"
                style={{
                  background: 'linear-gradient(135deg, #fbcfe8, #f9a8d4)',
                }}
              />
              {/* phone frame */}
              <div
                className="relative overflow-hidden rounded-[44px] bg-neutral-900 shadow-2xl"
                style={{
                  width: 240,
                  height: 500,
                  boxShadow:
                    '0 40px 80px -20px rgba(236,72,153,0.35), 0 0 0 1px rgba(255,255,255,0.1)',
                }}
              >
                {/* dynamic island */}
                <div className="absolute left-1/2 top-3 z-20 h-6 w-20 -translate-x-1/2 rounded-full bg-neutral-900" />
                {/* status bar */}
                <div className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-5 pt-2">
                  <div className="h-1.5 w-8 rounded-full bg-white/20" />
                  <div className="flex gap-1">
                    <div className="h-1.5 w-4 rounded-full bg-white/20" />
                    <div className="h-1.5 w-3 rounded-full bg-white/20" />
                  </div>
                </div>
                {/* screen */}
                <div className="absolute inset-0 overflow-hidden rounded-[44px]">
                  <div
                    key={step}
                    className="h-full w-full"
                    style={{
                      animation:
                        'screenSlideIn 0.45s cubic-bezier(0.34,1.56,0.64,1) both',
                    }}
                  >
                    <PhoneScreen screen={current.screen} />
                  </div>
                </div>
                {/* home indicator */}
                <div className="absolute bottom-2 left-1/2 h-1 w-24 -translate-x-1/2 rounded-full bg-white/20" />
              </div>

              {/* side button */}
              <div className="absolute -right-1 top-28 h-16 w-1.5 rounded-full bg-neutral-700" />
              <div className="absolute -left-1 top-20 h-10 w-1.5 rounded-full bg-neutral-700" />
              <div className="absolute -left-1 top-32 h-10 w-1.5 rounded-full bg-neutral-700" />
            </div>
          </div>
        </div>

        {/* scroll hint (첫 번째 스텝에서만) */}
        {step === 0 && (
          <div
            className="absolute bottom-8 left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 text-text-warm-300"
            style={{ animation: 'scrollHint 2s ease-in-out infinite' }}
          >
            <span className="text-xs font-medium">스크롤하여 계속</span>
            <div className="flex h-8 w-5 items-start justify-center rounded-full border-2 border-neutral-300 pt-1.5">
              <div
                className="h-1.5 w-1 rounded-full bg-primary-300"
                style={{ animation: 'scrollDot 2s ease-in-out infinite' }}
              />
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function TeamSection() {
  return (
    <section className="bg-neutral-50 px-6 py-20 md:py-28">
      <div className="mx-auto max-w-4xl">
        <RevealBox className="text-center">
          <h2 className="text-3xl font-extrabold tracking-[-0.04em] text-text-dark md:text-4xl">
            팀 소개
          </h2>
          <p className="mt-3 text-text-warm-300 md:text-lg">
            헤어때를 만든 사람들
          </p>
        </RevealBox>

        <div className="mt-14 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {TEAM.map((member, index) => (
            <RevealBox
              key={member.name}
              delay={index * 80}
              from={index % 2 === 0 ? 'left' : 'right'}
            >
              <TiltCard strength={12}>
                <a
                  href={member.github}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex flex-col items-center rounded-3xl border border-neutral-100 bg-white p-6 text-center transition-all duration-300 hover:border-primary-200 hover:shadow-[var(--shadow-pink-card)]"
                >
                  <div className="flex size-14 items-center justify-center rounded-full bg-primary-100 text-xl font-bold text-primary-300 transition-colors duration-300 group-hover:bg-primary-200">
                    {member.name[0]}
                  </div>
                  <p className="mt-3 text-sm font-bold text-text-dark">
                    {member.name}
                  </p>
                  <div className="mt-2 flex flex-wrap justify-center gap-1">
                    {member.roles.map((role) => (
                      <span
                        key={role}
                        className="rounded-full px-2 py-0.5 text-[10px] font-semibold"
                        style={{
                          background:
                            role === 'Back-end'
                              ? 'var(--color-neutral-100)'
                              : role === 'AI'
                                ? '#ede9fe'
                                : 'var(--color-primary-100)',
                          color:
                            role === 'Back-end'
                              ? 'var(--color-text-warm-300)'
                              : role === 'AI'
                                ? '#7c3aed'
                                : 'var(--color-primary-300)',
                        }}
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                </a>
              </TiltCard>
            </RevealBox>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Landing() {
  const scrolled = useScrolled()

  // hero mouse spotlight
  const [mousePos, setMousePos] = useState({ x: 50, y: 50 })
  const heroRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = heroRef.current
    if (!el) return

    const handleHeroMouseMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect()
      setMousePos({
        x: ((e.clientX - rect.left) / rect.width) * 100,
        y: ((e.clientY - rect.top) / rect.height) * 100,
      })
    }

    el.addEventListener('mousemove', handleHeroMouseMove)

    return () => {
      el.removeEventListener('mousemove', handleHeroMouseMove)
    }
  }, [])

  // 타이핑 순환 텍스트
  const [hairIndex, setHairIndex] = useState(0)
  const [typing, setTyping] = useState(true)
  const [displayed, setDisplayed] = useState('')
  const [charIndex, setCharIndex] = useState(0)

  useEffect(() => {
    const target = HAIR_WORDS[hairIndex]
    if (typing) {
      if (charIndex < target.length) {
        const timer = setTimeout(() => {
          setDisplayed(target.slice(0, charIndex + 1))
          setCharIndex((c) => c + 1)
        }, 80)
        return () => clearTimeout(timer)
      } else {
        const timer = setTimeout(() => setTyping(false), 1800)
        return () => clearTimeout(timer)
      }
    } else {
      if (charIndex > 0) {
        const timer = setTimeout(() => {
          setDisplayed(target.slice(0, charIndex - 1))
          setCharIndex((c) => c - 1)
        }, 40)
        return () => clearTimeout(timer)
      } else {
        setHairIndex((i) => (i + 1) % HAIR_WORDS.length)
        setTyping(true)
      }
    }
  }, [hairIndex, typing, charIndex])

  return (
    <div
      id="landing-scroll"
      className="fixed inset-0 z-50 w-screen overflow-y-auto bg-white"
      style={{ cursor: 'none' }}
    >
      <CustomCursor />
      <style>{`
        @keyframes blobFloat1 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(-20px, 20px) scale(1.05); }
        }
        @keyframes blobFloat2 {
          0%, 100% { transform: translate(0, 0) scale(1); }
          50% { transform: translate(20px, -20px) scale(1.08); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(24px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cursorBlink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes onboardFadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes screenSlideIn {
          from { opacity: 0; transform: scale(0.94) translateY(12px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes scrollHint {
          0%, 100% { opacity: 0.6; transform: translateX(-50%) translateY(0); }
          50% { opacity: 1; transform: translateX(-50%) translateY(4px); }
        }
        @keyframes scrollDot {
          0% { transform: translateY(0); opacity: 1; }
          100% { transform: translateY(10px); opacity: 0; }
        }
      `}</style>

      {/* ── 스크롤 진행 바 ── */}
      <ScrollProgressBar />

      {/* ── 헤더 ── */}
      <header
        className="sticky top-0 z-10 transition-all duration-300"
        style={{
          background: scrolled ? 'rgba(255,255,255,0.95)' : 'transparent',
          borderBottom: scrolled
            ? '1px solid var(--color-neutral-100)'
            : '1px solid transparent',
          backdropFilter: scrolled ? 'blur(12px)' : 'none',
          boxShadow: scrolled ? '0 1px 12px rgba(0,0,0,0.06)' : 'none',
        }}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <span className="font-display text-2xl font-bold tracking-[-0.04em] text-primary-300">
            헤어때
          </span>
          <div className="flex items-center gap-3">
            <Link
              to="/auth/login"
              className="rounded-full px-5 py-2 text-sm font-medium text-text-warm-500 transition-colors hover:bg-primary-50"
            >
              로그인
            </Link>
            <Link
              to="/auth/signup"
              className="rounded-full bg-primary-300 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-primary-hover hover:shadow-[var(--shadow-pink-sm)]"
            >
              시작하기
            </Link>
          </div>
        </div>
      </header>

      {/* ── 히어로 ── */}
      <section
        ref={heroRef}
        className="relative overflow-hidden bg-gradient-to-br from-primary-50 via-white to-primary-100 px-6 py-24 md:py-36"
      >
        {/* mouse spotlight */}
        <div
          className="pointer-events-none absolute inset-0 transition-opacity duration-300"
          style={{
            background: `radial-gradient(500px circle at ${mousePos.x}% ${mousePos.y}%, rgba(249,168,212,0.18), transparent 70%)`,
          }}
        />
        <div
          className="pointer-events-none absolute -right-40 -top-40 size-[600px] rounded-full bg-primary-100 opacity-50 blur-3xl"
          style={{ animation: 'blobFloat1 8s ease-in-out infinite' }}
        />
        <div
          className="pointer-events-none absolute -bottom-32 -left-32 size-[500px] rounded-full bg-primary-150 opacity-40 blur-3xl"
          style={{ animation: 'blobFloat2 10s ease-in-out infinite' }}
        />

        <div className="relative mx-auto max-w-4xl text-center">
          <span
            className="inline-block rounded-full bg-primary-100 px-4 py-1.5 text-sm font-semibold text-primary-300"
            style={{ animation: 'fadeSlideUp 0.6s ease both' }}
          >
            AI 헤어스타일 시뮬레이터
          </span>

          <h1
            className="mt-6 text-4xl font-extrabold leading-tight tracking-[-0.04em] text-text-dark md:text-6xl lg:text-7xl"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.1s both' }}
          >
            내 얼굴에 어울리는
            <br />
            <span className="inline-flex items-center text-primary-300">
              {displayed}
              <span
                className="ml-0.5 inline-block w-[3px] rounded-full bg-primary-300"
                style={{
                  animation: 'cursorBlink 0.8s step-end infinite',
                  height: '0.85em',
                  verticalAlign: 'middle',
                  display: 'inline-block',
                }}
              />
            </span>
            <br />
            지금 바로 체험해보세요
          </h1>

          <p
            className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-text-warm-300 md:text-lg"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.2s both' }}
          >
            카메라 하나로 수백 가지 헤어스타일을 가상으로 적용해보고, AI가
            분석한 맞춤 추천까지 받아보세요.
          </p>

          <div
            className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.3s both' }}
          >
            <Link
              to="/auth/signup"
              className="group relative w-full overflow-hidden rounded-full bg-primary-300 px-8 py-4 text-base font-bold text-white shadow-[var(--shadow-pink-md)] transition-all hover:shadow-[var(--shadow-pink-sm)] sm:w-auto"
            >
              <span className="relative z-10">무료로 시작하기</span>
              <span className="absolute inset-0 -translate-x-full bg-primary-hover transition-transform duration-300 group-hover:translate-x-0" />
            </Link>
            <Link
              to="/auth/login"
              className="w-full rounded-full border border-primary-200 bg-white px-8 py-4 text-base font-semibold text-primary-300 transition-colors hover:bg-primary-50 sm:w-auto"
            >
              로그인하기
            </Link>
          </div>

          <p
            className="mt-4 text-sm text-text-warm-300"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.4s both' }}
          >
            회원가입 무료 · 별도 앱 설치 불필요
          </p>
        </div>
      </section>

      {/* ── 통계 카운터 ── */}
      <StatsSection />

      {/* ── 기능 탭 ── */}
      <FeatureTabs />

      {/* ── 서비스 온보딩 ── */}
      <OnboardingSection />

      {/* ── 팀 소개 ── */}
      <TeamSection />

      {/* ── CTA ── */}
      <section className="relative overflow-hidden bg-gradient-to-br from-primary-300 to-primary-400 px-6 py-20 md:py-28">
        <div
          className="pointer-events-none absolute -right-20 -top-20 size-96 rounded-full bg-white opacity-10 blur-3xl"
          style={{ animation: 'blobFloat1 7s ease-in-out infinite' }}
        />
        <div
          className="pointer-events-none absolute -bottom-20 -left-20 size-80 rounded-full bg-white opacity-10 blur-3xl"
          style={{ animation: 'blobFloat2 9s ease-in-out infinite' }}
        />

        <RevealBox className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-extrabold tracking-[-0.04em] text-white md:text-5xl">
            지금 바로 헤어때를
            <br />
            시작해보세요
          </h2>
          <p className="mt-4 text-base text-white/80 md:text-lg">
            AI가 추천하는 나만의 헤어스타일을 찾아보세요
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              to="/auth/signup"
              className="group relative w-full overflow-hidden rounded-full bg-white px-10 py-4 text-base font-bold text-primary-300 shadow-md transition-all hover:shadow-lg sm:w-auto"
            >
              <span className="relative z-10">무료 회원가입</span>
              <span className="absolute inset-0 -translate-x-full bg-primary-50 transition-transform duration-300 group-hover:translate-x-0" />
            </Link>
            <Link
              to="/auth/login"
              className="w-full rounded-full border-2 border-white/70 px-10 py-4 text-base font-semibold text-white transition-all hover:bg-white/10 sm:w-auto"
            >
              로그인
            </Link>
          </div>
        </RevealBox>
      </section>

      {/* ── 푸터 ── */}
      <footer className="bg-text-dark px-6 py-10">
        <div className="mx-auto max-w-6xl text-center">
          <span className="font-display text-xl font-bold tracking-[-0.04em] text-primary-250">
            헤어때
          </span>
          <p className="mt-3 text-sm text-neutral-400">
            © 2025 헤어때. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
