import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'

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
  const [activeSlide, setActiveSlide] = useState(0)

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setActiveSlide((prev) => (prev + 1) % slides.length)
    }, 3000)

    return () => window.clearInterval(intervalId)
  }, [])

  const currentSlide = slides[activeSlide]

  return (
    <main className="app-frame-page flex flex-col overflow-hidden bg-bg-primary px-6 pt-16 text-[#2f2f2f]">
      <div className="mx-auto flex w-full max-w-[390px] flex-1 flex-col">
        <section className="flex flex-col items-center">
          <h1 className="whitespace-pre-line px-8 text-center text-[20px] leading-[1.35] font-semibold tracking-[-0.03em] text-[#2f2f2f]">
            {currentSlide.title}
          </h1>

          <div className="mt-[92px] flex w-full justify-center px-5">
            <img
              src={currentSlide.imageSrc}
              alt={currentSlide.imageAlt}
              width={398}
              height={320}
              loading="eager"
              decoding="async"
              className="h-auto w-full max-w-[398px] object-contain"
              draggable={false}
            />
          </div>

          <div className="mt-[30px] flex items-center justify-center gap-[7px]">
            {slides.map((slide, index) => (
              <span
                key={slide.imageSrc}
                className={`block size-[10px] rounded-full transition-colors ${
                  index === activeSlide ? 'bg-[#f39ca6]' : 'bg-[#e3e3e8]'
                }`}
              />
            ))}
          </div>
        </section>

        <div className="mt-auto">
          <Button
            asChild
            className="h-14 w-full rounded-[8px] bg-[#ea7589] px-6 py-4 text-base font-medium leading-[1.4] text-[#f2f2f7] hover:bg-[#e1637b]"
          >
            <Link to="/auth/login">헤어 어때 시작하기</Link>
          </Button>
        </div>
      </div>
    </main>
  )
}
