import { Link } from '@tanstack/react-router'
import { Camera, Check, Layers, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { usePwaInstall } from '@/hooks/use-pwa-install'

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
      const scrolled = Math.max(0, -top)
      const total = height - viewH
      const p = total > 0 ? Math.max(0, Math.min(1, scrolled / total)) : 0
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
  '단발펌',
  '리젠트컷',
  '댄디컷',
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
    title: 'AR 가상 헤어 체험',
    description:
      '카메라를 켜는 순간, AI가 얼굴을 자동 인식하고 원하는 헤어스타일을 실시간으로 입혀드려요. 미용실 가기 전에 먼저 체험해보세요.',
    points: ['얼굴형 자동 인식', '실시간 AR 렌더링', '결과 사진 저장'],
  },
  {
    id: 'recommend',
    icon: Sparkles,
    label: '데이터 기반 추천',
    badge: '데이터 분석',
    title: '사용자 행동 기반 추천',
    description:
      '실제 사용자들의 경험을 기반으로 분석하여 가장 어울리는 헤어스타일을 골라드려요.',
    points: [
      '실제 사용자 데이터 기반',
      '트렌드 반영 업데이트',
      '인기순·최신순 정렬',
    ],
  },
  {
    id: 'explore',
    icon: Layers,
    label: '카테고리 탐색',
    badge: '트렌드',
    title: '수십 가지 스타일을 한눈에',
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
  image: string
  phoneBg?: string
}

const ONBOARDING: OnboardingStep[] = [
  {
    step: '01',
    title: '나만의 맞춤 시작',
    description:
      '더 정확한 맞춤 서비스를 위해 간단한 정보를 입력하고 가입을 완료해 보세요.',
    color: 'from-pink-50 to-rose-100',
    image: '/images/sign-up.png',
  },
  {
    step: '02',
    title: '스타일 탐색',
    description:
      '숏컷·미디엄·롱까지 수십 가지 스타일을 카테고리별로 자유롭게 둘러보세요.',
    color: 'from-fuchsia-50 to-pink-100',
    image: '/images/main.png',
  },
  {
    step: '03',
    title: '실시간 헤어 피팅',
    description:
      '카메라를 켜면 내 얼굴에 딱 맞는 다양한 헤어스타일을 실시간으로 입혀볼 수 있어요.',
    color: 'from-rose-50 to-pink-100',
    image: '/images/camera.png',
    phoneBg: '#000',
  },
  {
    step: '04',
    title: '결과 저장',
    description:
      '마음에 든 스타일을 저장하고, 디자이너와 더욱 자세하게 소통해보세요.',
    color: 'from-pink-50 to-fuchsia-100',
    image: '/images/result.png',
    phoneBg: '#000',
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
  const styles = useCounter(40, 1600, visible)
  const satisfaction = useCounter(98, 1400, visible)
  const users = useCounter(2, 1200, visible)

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
          { value: users, suffix: '천+', unit: '', label: '누적 체험 수' },
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

// ─── Phone Preview ────────────────────────────────────────────────────────────

function AppPreviewPhone({ src, bg }: { src: string; bg?: string }) {
  return (
    <div
      className="relative h-full w-full bg-neutral-100"
      style={bg ? { background: bg } : undefined}
    >
      <img
        src={src}
        alt="헤어때 앱 미리보기"
        className="h-full w-full object-contain"
        loading="lazy"
      />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/35 to-transparent" />
    </div>
  )
}

// ─── Phone Mockup ─────────────────────────────────────────────────────────────

function PhoneMockup({
  src,
  bg,
  floatDown,
}: {
  src: string
  bg?: string
  floatDown?: boolean
}) {
  return (
    <div
      className="relative transition-all duration-700"
      style={{ transform: `translateY(${floatDown ? '8px' : '-8px'})` }}
    >
      <div
        className="absolute -inset-5 rounded-full opacity-40 blur-3xl transition-all duration-700 md:-inset-8"
        style={{ background: 'linear-gradient(135deg, #fbcfe8, #f9a8d4)' }}
      />
      <div
        className="relative h-[430px] w-[210px] overflow-hidden rounded-[38px] bg-neutral-900 sm:h-[470px] sm:w-[230px] md:h-[500px] md:w-[240px] md:rounded-[44px]"
        style={{
          boxShadow:
            '0 40px 80px -20px rgba(236,72,153,0.35), 0 0 0 1px rgba(255,255,255,0.1)',
        }}
      >
        <div className="absolute left-1/2 top-3 z-20 h-5 w-[72px] -translate-x-1/2 rounded-full bg-neutral-900 md:h-6 md:w-20" />
        <div className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-4 pt-2 md:px-5">
          <div className="h-1.5 w-8 rounded-full bg-white/20" />
          <div className="flex gap-1">
            <div className="h-1.5 w-4 rounded-full bg-white/20" />
            <div className="h-1.5 w-3 rounded-full bg-white/20" />
          </div>
        </div>
        <div className="absolute inset-0 overflow-hidden rounded-[44px]">
          <div className="h-full w-full">
            <AppPreviewPhone src={src} bg={bg} />
          </div>
        </div>
        <div className="absolute bottom-2 left-1/2 h-1 w-20 -translate-x-1/2 rounded-full bg-white/20 md:w-24" />
      </div>
      <div className="absolute -right-1 top-24 h-14 w-1.5 rounded-full bg-neutral-700 md:top-28 md:h-16" />
      <div className="absolute -left-1 top-[4.5rem] h-9 w-1.5 rounded-full bg-neutral-700 md:top-20 md:h-10" />
      <div className="absolute -left-1 top-28 h-9 w-1.5 rounded-full bg-neutral-700 md:top-32 md:h-10" />
    </div>
  )
}

// ─── Onboarding Section ───────────────────────────────────────────────────────

function OnboardingSection() {
  const { outerRef, step } = useOnboardingStep(ONBOARDING.length)
  const current = ONBOARDING[step]

  return (
    <>
      {/* 모바일: 4단계 정적 카드 */}
      <section className="bg-white px-6 py-14 md:hidden">
        <div className="mx-auto max-w-md space-y-16">
          {ONBOARDING.map((s, i) => (
            <RevealBox key={s.step} delay={i * 60}>
              <div
                className={`relative overflow-hidden rounded-3xl bg-gradient-to-br ${s.color} p-1`}
              >
                <div className="rounded-[20px] bg-white p-6">
                  <div className="mb-4 flex justify-center">
                    <PhoneMockup
                      src={s.image}
                      bg={s.phoneBg}
                      floatDown={i % 2 !== 0}
                    />
                  </div>
                  <span className="inline-block rounded-full bg-primary-100 px-3 py-1 text-xs font-bold text-primary-300">
                    STEP {s.step}
                  </span>
                  <h3 className="mt-3 break-keep text-xl font-extrabold tracking-[-0.03em] text-text-dark">
                    {s.title}
                  </h3>
                  <p className="mt-2 break-keep text-sm leading-relaxed text-text-warm-300">
                    {s.description}
                  </p>
                </div>
              </div>
            </RevealBox>
          ))}
        </div>
      </section>

      {/* 데스크톱: 스크롤 드리븐 sticky */}
      <section ref={outerRef} className="relative hidden md:block md:h-[400vh]">
        <div className="flex h-screen items-center overflow-hidden bg-white md:sticky md:top-0">
          <div
            className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${current.color} opacity-30 transition-all duration-700`}
          />

          <div className="relative mx-auto grid w-full max-w-6xl grid-cols-2 items-center gap-12 px-6">
            {/* 텍스트 영역 */}
            <div>
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
                <h2 className="mt-4 break-keep text-4xl font-extrabold tracking-[-0.04em] text-text-dark lg:text-5xl">
                  {current.title}
                </h2>
                <p className="mt-4 max-w-md break-keep text-base leading-relaxed text-text-warm-300 md:text-lg">
                  {current.description}
                </p>
              </div>

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
                        color:
                          i === step ? '#fff' : 'var(--color-text-warm-300)',
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
            <div className="flex justify-center">
              <PhoneMockup
                src={current.image}
                bg={current.phoneBg}
                floatDown={step % 2 !== 0}
              />
            </div>
          </div>

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
    </>
  )
}

function TeamSection() {
  return (
    <section className="bg-neutral-50 px-6 py-20 md:py-28">
      <div className="mx-auto max-w-4xl">
        <RevealBox className="text-center">
          <h2 className="text-3xl font-extrabold tracking-[-0.04em] text-text-dark md:text-4xl">
            Me:ah
          </h2>
          <p className="mt-3 text-text-warm-300 md:text-lg">
            당신의 새로운 헤어스타일을 위해 모인 사람들, Me:ah 팀을 소개해요.
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
                  className="group flex flex-col items-center rounded-3xl border border-neutral-100 bg-white p-6 text-center transition-all duration-300 hover:shadow-[var(--shadow-pink-card)]"
                >
                  <div className="relative flex size-14 items-center justify-center rounded-full bg-primary-100 text-xl font-bold text-primary-300 transition-colors duration-300 group-hover:bg-primary-200">
                    <span className="transition-opacity duration-300 group-hover:opacity-0">
                      {member.name[0]}
                    </span>
                    <img
                      src="/images/github-logo.png"
                      alt="GitHub"
                      className="absolute inset-0 m-auto w-8 h-auto opacity-0 transition-opacity duration-300 group-hover:opacity-70"
                    />
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
  const pwaInstall = usePwaInstall()
  const showInstallPrimary =
    pwaInstall.showInstallPrompt || pwaInstall.showIosInstallHint
  const heroPrimaryLabel = pwaInstall.showInstallPrompt
    ? '앱 설치하기'
    : pwaInstall.showIosInstallHint
      ? '홈 화면에 추가'
      : '무료로 시작하기'
  const heroSupportCopy = pwaInstall.showInstallPrompt
    ? '설치 후 홈 화면에서 더 빠르게 헤어때를 실행할 수 있어요.'
    : pwaInstall.showIosInstallHint
      ? 'iPhone Safari에서는 공유 메뉴에서 홈 화면에 추가를 선택해 주세요.'
      : '설치 지원이 없는 환경에서는 웹에서 바로 시작할 수 있어요.'

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
            카메라 하나로 수십 가지 헤어스타일을 가상으로 적용해보고, 사용자
            행동 데이터를 기반으로 한 맞춤 추천까지 받아보세요.
          </p>

          <div
            className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.3s both' }}
          >
            {pwaInstall.showInstallPrompt ? (
              <button
                type="button"
                className="group relative w-full overflow-hidden rounded-full bg-primary-300 px-8 py-4 text-base font-bold text-white shadow-[var(--shadow-pink-md)] transition-all hover:shadow-[var(--shadow-pink-sm)] sm:w-auto"
                onClick={() => {
                  void (async () => {
                    const choice = await pwaInstall.promptInstall()
                    if (!choice || choice.outcome !== 'accepted') {
                      pwaInstall.dismissInstallPrompt()
                    }
                  })()
                }}
              >
                <span className="relative z-10">{heroPrimaryLabel}</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-hover transition-transform duration-300 group-hover:translate-x-0" />
              </button>
            ) : pwaInstall.showIosInstallHint ? (
              <a
                href="#pwa-install-guide"
                className="group relative w-full overflow-hidden rounded-full bg-primary-300 px-8 py-4 text-center text-base font-bold text-white shadow-[var(--shadow-pink-md)] transition-all hover:shadow-[var(--shadow-pink-sm)] sm:w-auto"
              >
                <span className="relative z-10">{heroPrimaryLabel}</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-hover transition-transform duration-300 group-hover:translate-x-0" />
              </a>
            ) : (
              <Link
                to="/auth/signup"
                className="group relative w-full overflow-hidden rounded-full bg-primary-300 px-8 py-4 text-base font-bold text-white shadow-[var(--shadow-pink-md)] transition-all hover:shadow-[var(--shadow-pink-sm)] sm:w-auto"
              >
                <span className="relative z-10">{heroPrimaryLabel}</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-hover transition-transform duration-300 group-hover:translate-x-0" />
              </Link>
            )}
            {showInstallPrimary ? (
              <Link
                to="/auth/signup"
                className="w-full rounded-full border border-primary-200 bg-white px-8 py-4 text-center text-base font-semibold text-primary-300 transition-colors hover:bg-primary-50 sm:w-auto"
              >
                웹에서 바로 시작하기
              </Link>
            ) : null}
          </div>

          <div
            id="pwa-install-guide"
            className="mx-auto mt-4 max-w-2xl rounded-full bg-white/72 px-5 py-3 text-sm text-text-warm-300 shadow-[0_16px_40px_rgba(249,168,212,0.18)] backdrop-blur"
            style={{ animation: 'fadeSlideUp 0.6s ease 0.4s both' }}
          >
            {heroSupportCopy}
          </div>
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
            {showInstallPrimary ? '설치하고 더 빠르게' : '지금 바로 헤어때를'}
            <br />
            시작해보세요
          </h2>
          <p className="mt-4 text-base text-white/80 md:text-lg">
            {showInstallPrimary
              ? '홈 화면에서 바로 열고, 앱처럼 몰입감 있게 헤어때를 사용해보세요.'
              : 'AI가 추천하는 나만의 헤어스타일을 웹에서 바로 찾아보세요.'}
          </p>

          <div className="mt-10 flex justify-center">
            {pwaInstall.showInstallPrompt ? (
              <button
                type="button"
                className="group relative w-full overflow-hidden rounded-full bg-white px-10 py-4 text-base font-bold text-primary-300 shadow-md transition-all hover:shadow-lg sm:w-auto"
                onClick={() => {
                  void (async () => {
                    const choice = await pwaInstall.promptInstall()
                    if (!choice || choice.outcome !== 'accepted') {
                      pwaInstall.dismissInstallPrompt()
                    }
                  })()
                }}
              >
                <span className="relative z-10">앱 설치하기</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-50 transition-transform duration-300 group-hover:translate-x-0" />
              </button>
            ) : pwaInstall.showIosInstallHint ? (
              <a
                href="#pwa-install-guide"
                className="group relative w-full overflow-hidden rounded-full bg-white px-10 py-4 text-center text-base font-bold text-primary-300 shadow-md transition-all hover:shadow-lg sm:w-auto"
              >
                <span className="relative z-10">홈 화면에 추가</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-50 transition-transform duration-300 group-hover:translate-x-0" />
              </a>
            ) : (
              <Link
                to="/auth/signup"
                className="group relative w-full overflow-hidden rounded-full bg-white px-10 py-4 text-base font-bold text-primary-300 shadow-md transition-all hover:shadow-lg sm:w-auto"
              >
                <span className="relative z-10">무료로 시작하기</span>
                <span className="absolute inset-0 -translate-x-full bg-primary-50 transition-transform duration-300 group-hover:translate-x-0" />
              </Link>
            )}
          </div>
          <p className="mt-5 text-sm text-white/80">
            계정이 있다면{' '}
            <Link
              to="/auth/login"
              className="font-semibold text-white underline underline-offset-4"
            >
              로그인
            </Link>
            , 설치 대신 웹에서 시작하려면{' '}
            <Link
              to="/auth/signup"
              className="font-semibold text-white underline underline-offset-4"
            >
              회원가입
            </Link>
            하세요.
          </p>
        </RevealBox>
      </section>

      {/* ── 푸터 ── */}
      <footer className="bg-text-dark px-6 py-10">
        <div className="mx-auto max-w-6xl text-center">
          <span className="font-display text-xl font-bold tracking-[-0.04em] text-primary-250">
            헤어때
          </span>
          <p className="mt-3 text-sm text-neutral-400">
            © 2026 Me:ah team 헤어때. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
