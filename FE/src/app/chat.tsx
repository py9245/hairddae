import { useSearch } from '@tanstack/react-router'

import { Header } from '@/components/header'

export default function Chat() {
  const search = useSearch({ from: '/chat' })

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="채팅" className="px-0 pb-3 pt-2" />

        <section className="mt-8 rounded-3xl bg-card p-6">
          <h1 className="text-xl font-bold text-text-dark">1:1 채팅</h1>
          <p className="mt-3 text-sm leading-6 text-text-sub">
            디자이너와 1:1 상담을 시작할 수 있도록 채팅방을 생성했습니다.
          </p>

          <div className="mt-5 rounded-2xl bg-primary-100/40 p-4">
            <p className="text-sm font-semibold text-text-dark">
              디자이너 ID: {search.designerUserId ?? '-'}
            </p>
            <p className="mt-2 text-sm text-text-sub">
              채팅방 ID: {search.roomId ?? '-'}
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
