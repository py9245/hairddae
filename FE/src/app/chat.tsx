import { Header } from '@/components/header'

export default function Chat() {
  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="채팅" className="px-0 pb-3 pt-2" />
        <section className="mt-8 rounded-3xl bg-card p-6 text-center">
          <h1 className="text-xl font-bold text-text-dark">채팅목록</h1>
        </section>
      </div>
    </main>
  )
}
