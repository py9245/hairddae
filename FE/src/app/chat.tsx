import { useSearch } from '@tanstack/react-router'
import { ChevronLeft, LoaderCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ChatMessageBubble } from '@/components/chat-message-bubble'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useChatMessagePolling } from '@/hooks/Chat/use-chat-message-polling'
import { getChatMessages, readChatRoomContext } from '@/lib/chat'

export default function Chat() {
  const search = useSearch({ from: '/chat' })
  const roomContext = readChatRoomContext()
  const roomId = search.roomId ?? null
  const designerUserId = search.designerUserId ?? roomContext?.designerUserId
  const [initialImageUrl, setInitialImageUrl] = useState<string | null>(null)

  const messagesQuery = useChatMessagePolling({
    roomId,
    enabled: roomId != null,
    fetcher: async (nextRoomId) => {
      const response = await getChatMessages(nextRoomId)

      return {
        done: false,
        data: response.messages,
        message: response.message,
      }
    },
  })

  useEffect(() => {
    const appliedImage =
      roomContext?.roomId?.toString() === roomId?.toString()
        ? (roomContext?.appliedImage ?? null)
        : null

    if (!appliedImage) {
      setInitialImageUrl(null)
      return
    }

    const nextUrl = URL.createObjectURL(appliedImage)
    setInitialImageUrl(nextUrl)

    return () => {
      URL.revokeObjectURL(nextUrl)
    }
  }, [roomContext, roomId])

  return (
    <main className="app-frame-page relative h-full overflow-hidden bg-bg-primary">
      <Header
        className="px-4 pt-4"
        leftAction={
          <Button
            type="button"
            variant="outline"
            size="icon-sm"
            aria-label="이전으로 이동"
            onClick={() => window.history.back()}
          >
            <ChevronLeft className="size-5" />
          </Button>
        }
        centerContent={
          <div className="text-center">
            <p className="text-sm font-semibold text-text-sub">1:1 채팅</p>
            <p className="text-base font-bold text-text-dark">
              {designerUserId ?? '디자이너'}
            </p>
          </div>
        }
      />

      <div className="mx-auto flex h-full w-full max-w-[390px] flex-col px-4 pb-[108px] pt-20">
        <section className="rounded-[28px] bg-[linear-gradient(180deg,#FFFFFF_0%,#F9EFF1_100%)] p-4 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
          <p className="text-sm font-semibold text-primary-300">
            상담이 시작되었어요
          </p>
          <p className="mt-2 text-sm leading-6 text-text-sub">
            적용한 이미지를 먼저 전달했고, 이후 메시지는 폴링으로 불러옵니다.
          </p>
        </section>

        <section className="mt-4 flex-1 space-y-4 overflow-y-auto rounded-[28px] bg-card p-4 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
          {initialImageUrl ? (
            <ChatMessageBubble
              align="right"
              imageUrl={initialImageUrl}
              caption="적용 이미지"
            />
          ) : null}

          {messagesQuery.isPolling && !messagesQuery.data?.length ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-sub">
              <LoaderCircle className="size-4 animate-spin" />
              메시지를 불러오고 있습니다.
            </div>
          ) : null}

          {messagesQuery.data?.map((message) => (
            <ChatMessageBubble
              key={String(message.id)}
              align={message.senderUserId === designerUserId ? 'left' : 'right'}
              text={message.messageText}
              imageUrl={message.imageUrl}
            />
          ))}

          {!initialImageUrl && !messagesQuery.data?.length ? (
            <div className="flex h-full items-center justify-center py-10 text-sm text-text-sub">
              아직 주고받은 메시지가 없습니다.
            </div>
          ) : null}

          {messagesQuery.isError ? (
            <p className="text-sm text-error" role="alert">
              {messagesQuery.message ?? '채팅 메시지를 불러오지 못했습니다.'}
            </p>
          ) : null}
        </section>

        <section className="mt-4 rounded-[24px] bg-card p-4 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
          <div className="rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm text-text-sub">
            메시지 전송 입력창은 다음 단계에서 연결합니다.
          </div>
        </section>
      </div>
    </main>
  )
}
