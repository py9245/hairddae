import { Image as ImageIcon, LoaderCircle } from 'lucide-react'

import { Header } from '@/components/header'
import type { ChatRoomListItem } from '@/lib/chat'

type ChatRoomListViewProps = {
  rooms: ChatRoomListItem[]
  isLoading: boolean
  errorMessage: string | null
  onEnterRoom: (room: ChatRoomListItem) => void
}

export function ChatRoomListView({
  rooms,
  isLoading,
  errorMessage,
  onEnterRoom,
}: ChatRoomListViewProps) {
  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="채팅목록" className="px-0 pb-3 pt-2" />

        {isLoading ? (
          <div className="mt-6 flex items-center justify-center gap-2 rounded-[28px] bg-card px-5 py-10 text-sm text-text-sub shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
            <LoaderCircle className="size-4 animate-spin" />
            채팅방 목록을 불러오고 있습니다.
          </div>
        ) : null}

        {errorMessage ? (
          <div
            className="mt-6 rounded-[28px] bg-card px-5 py-10 text-center text-sm text-error shadow-[0_18px_36px_rgba(15,23,42,0.08)]"
            role="alert"
          >
            {errorMessage}
          </div>
        ) : null}

        {!isLoading && !errorMessage ? (
          <section className="mt-5 flex flex-col gap-4 pb-6">
            {rooms.length > 0 ? (
              rooms.map((room) => (
                <button
                  key={String(room.roomId)}
                  type="button"
                  className="overflow-hidden rounded-[28px] bg-card text-left shadow-[0_18px_36px_rgba(15,23,42,0.08)] transition hover:-translate-y-0.5"
                  onClick={() => onEnterRoom(room)}
                >
                  <div className="flex items-stretch gap-4 p-5">
                    <div className="flex min-w-0 flex-1 flex-col">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-base font-bold text-text-dark">
                          {room.designerUserId}
                        </p>
                        <p className="shrink-0 text-xs text-text-sub">
                          {room.updatedAt ?? ''}
                        </p>
                      </div>

                      <div className="mt-3">
                        {room.lastMessageType === 'IMAGE' &&
                        room.lastImageUrl ? (
                          <div className="flex items-center gap-2 text-sm text-text-sub">
                            <ImageIcon className="size-4 text-primary-300" />
                            사진을 보냈습니다.
                          </div>
                        ) : (
                          <p className="line-clamp-2 text-sm leading-6 text-text-sub">
                            {room.lastMessageText ?? '메시지가 없습니다.'}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-[28px] bg-card px-5 py-10 text-center shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
                <p className="text-base font-semibold text-text-dark">
                  아직 채팅방이 없습니다.
                </p>
                <p className="mt-2 text-sm leading-6 text-text-sub">
                  디자이너를 선택해 상담을 시작해 보세요.
                </p>
              </div>
            )}
          </section>
        ) : null}
      </div>
    </main>
  )
}
