import Autoplay from 'embla-carousel-autoplay'
import useEmblaCarousel from 'embla-carousel-react'
import { ExternalLink, Globe, Instagram, Youtube } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

type AdsenseProps = {
  loading?: boolean
  forceVisible?: boolean
}

const ssafySlides = [
  {
    title: 'SSAFY 공식 홈페이지',
    href: 'https://share.google/WgazIqR7qEnrxeYy3',
    icon: Globe,
    accent: 'from-[#2563eb] to-[#0f172a]',
    description: '교육 과정, 지원 정보, SSAFY 소개를 한 번에 확인해 보세요.',
  },
  {
    title: 'SSAFY 공식 유튜브',
    href: 'https://www.youtube.com/@hellossafy/featured',
    icon: Youtube,
    accent: 'from-[#ef4444] to-[#b91c1c]',
    description: '현장 이야기와 프로그램 소개 영상을 볼 수 있어요.',
  },
  {
    title: 'SSAFY 공식 인스타그램',
    href: 'https://www.instagram.com/hellossafy/',
    icon: Instagram,
    accent: 'from-[#f97316] via-[#ec4899] to-[#7c3aed]',
    description: '최신 소식과 분위기를 빠르게 확인할 수 있어요.',
  },
] as const

export default function Adsense({
  loading = false,
  forceVisible = false,
}: AdsenseProps) {
  const autoplayPlugin = useMemo(
    () =>
      Autoplay({
        delay: 3000,
        stopOnInteraction: false,
        stopOnMouseEnter: true,
      }),
    [],
  )

  const [emblaRef, emblaApi] = useEmblaCarousel(
    {
      loop: true,
      align: 'start',
      dragFree: false,
    },
    loading ? [] : [autoplayPlugin],
  )

  const [activeIndex, setActiveIndex] = useState(0)

  const onSelect = useCallback(() => {
    if (!emblaApi) return
    setActiveIndex(emblaApi.selectedScrollSnap())
  }, [emblaApi])

  useEffect(() => {
    if (!emblaApi) return
    onSelect()
    emblaApi.on('select', onSelect)
    emblaApi.on('reInit', onSelect)

    return () => {
      emblaApi.off('select', onSelect)
      emblaApi.off('reInit', onSelect)
    }
  }, [emblaApi, onSelect])

  function goToSlide(index: number) {
    emblaApi?.scrollTo(index)
  }

  return (
    <aside
      className={
        forceVisible
          ? 'block w-[450px] shrink-0'
          : 'hidden w-[450px] shrink-0 xl:block'
      }
    >
      <div className="sticky top-6 overflow-hidden rounded-[28px] border border-primary-100 bg-white shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
        <div className="px-4 py-4">
          {loading ? (
            <div className="h-[196px] animate-pulse rounded-3xl border border-slate-200 bg-slate-100" />
          ) : (
            <div
              className="overflow-hidden rounded-3xl border border-slate-200 bg-white"
              ref={emblaRef}
            >
              <div className="flex">
                {ssafySlides.map(
                  ({ title, href, icon: Icon, accent, description }) => (
                    <div key={title} className="min-w-0 flex-[0_0_100%] p-4">
                      <a
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                        className="group block"
                        draggable={false}
                      >
                        <div className="flex items-start gap-3">
                          <div
                            className={`flex size-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br ${accent} text-white shadow-sm`}
                          >
                            <Icon className="size-5" />
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-semibold text-slate-900">
                                {title}
                              </p>
                              <ExternalLink className="size-4 shrink-0 text-slate-400 transition-colors group-hover:text-primary-300" />
                            </div>

                            <p className="mt-1 text-sm leading-6 text-slate-600">
                              {description}
                            </p>

                            <p className="mt-3 truncate text-xs text-slate-400">
                              {href}
                            </p>
                          </div>
                        </div>
                      </a>
                    </div>
                  ),
                )}
              </div>
            </div>
          )}

          {!loading ? (
            <div className="mt-4 flex items-center justify-between gap-3 px-1">
              <div className="flex items-center gap-2">
                {ssafySlides.map((slide, index) => (
                  <button
                    key={slide.title}
                    type="button"
                    onClick={() => goToSlide(index)}
                    aria-label={`${slide.title} 보기`}
                    className={`h-2.5 rounded-full transition-all ${
                      index === activeIndex
                        ? 'w-6 bg-primary-300'
                        : 'w-2.5 bg-slate-300'
                    }`}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </aside>
  )
}
