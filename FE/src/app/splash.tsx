import { Link } from '@tanstack/react-router'
import Autoplay from 'embla-carousel-autoplay'
import useEmblaCarousel from 'embla-carousel-react'
import { useCallback, useEffect, useState } from 'react'

import { SplashStartButton } from '@/components/splash-start-button'

const slides = [
  {
    title: '내가 원하는 헤어를\n마음껏 착용해 보아요.',
    imageSrc: '/icon/splash-01.svg',
    imageAlt: '헤어 가상 착용을 보여주는 카메라 일러스트',
  },
  {
    title: '인기있는 스타일과 함께\n디자이너와 소통해요',
    imageSrc: '/icon/splash-02.svg',
    imageAlt: '인기 헤어 스타일과 디자이너 소통을 보여주는 일러스트',
  },
  {
    title: '다양한 종류의 헤어를\n찾아볼 수 있어요',
    imageSrc: '/icon/splash-03.svg',
    imageAlt: '다양한 헤어 스타일 탐색을 보여주는 일러스트',
  },
] as const

export default function Splash() {
  const [emblaRef, emblaApi] = useEmblaCarousel({ loop: true }, [
    Autoplay({ delay: 3000, stopOnInteraction: false }),
  ])
  const [activeSlide, setActiveSlide] = useState(0)

  const onSelect = useCallback(() => {
    if (!emblaApi) return
    setActiveSlide(emblaApi.selectedScrollSnap())
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

  return (
    <main className="app-frame-page flex flex-col overflow-hidden bg-bg-primary px-6 pt-16 text-text-dark">
      <div className="mx-auto flex w-full max-w-[390px] flex-1 flex-col">
        {/* Carousel Viewport */}
        <div className="min-h-[600px] w-full overflow-hidden" ref={emblaRef}>
          {/* Carousel Container */}
          <div className="flex">
            {slides.map((slide, index) => (
              <div className="min-w-0 flex-[0_0_100%]" key={slide.imageSrc}>
                <section className="flex flex-col items-center">
                  <h1 className="h-[54px] whitespace-pre-line px-8 text-center text-[20px] leading-[1.35] font-semibold tracking-[-0.03em] text-text-dark">
                    {slide.title}
                  </h1>

                  <div className="mt-[92px] flex w-full justify-center px-5">
                    <img
                      src={slide.imageSrc}
                      alt={slide.imageAlt}
                      width={398}
                      height={320}
                      loading={index === 0 ? 'eager' : 'lazy'}
                      decoding="async"
                      className="h-auto w-full max-w-[398px] object-contain select-none"
                      draggable={false}
                    />
                  </div>
                </section>
              </div>
            ))}
          </div>
        </div>

        {/* Indicators */}
        <div className="mt-[30px] flex items-center justify-center gap-[7px]">
          {slides.map((slide, index) => (
            <span
              key={slide.imageSrc}
              className={`block size-[10px] rounded-full transition-colors ${
                index === activeSlide
                  ? 'bg-indicator-active'
                  : 'bg-indicator-inactive'
              }`}
            />
          ))}
        </div>

        <div className="mt-auto">
          <SplashStartButton asChild>
            <Link to="/auth/login">헤어 어때 시작하기</Link>
          </SplashStartButton>
        </div>
      </div>
    </main>
  )
}
