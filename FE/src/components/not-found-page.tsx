import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <main className="app-frame-page flex flex-col bg-bg-primary px-6">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col">
        <section className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
          <img
            src="/icon/not-found.svg"
            alt="페이지를 찾을 수 없음"
            className="w-full max-w-[260px]"
            draggable={false}
          />
          <p className="text-xs font-semibold uppercase tracking-[0.35em]">
            Not Found
          </p>
          <h1 className="text-[1.5rem] font-semibold leading-[1.3] tracking-[-0.03em]">
            페이지를 찾을 수 없어요
          </h1>
        </section>

        <div className="mt-auto grid gap-3">
          <Button
            className="h-14 rounded-[8px] bg-primary-300 text-base font-medium"
            onClick={() => history.back()}
          >
            돌아가기
          </Button>
        </div>
      </div>
    </main>
  )
}
