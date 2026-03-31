import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'
import {
  ChevronLeft,
  Image as ImageIcon,
  LoaderCircle,
  SendHorizonal,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { ChatMessageBubble } from '@/components/chat-message-bubble'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useChatMessagePolling } from '@/hooks/Chat/use-chat-message-polling'
import {
  type ChatMessage,
  type ChatRoomListItem,
  getChatMessages,
  getChatRooms,
  readChatRoomContext,
  sendChatMessage,
} from '@/lib/chat'

function getLastMessageId(messages: ChatMessage[]) {
  if (messages.length === 0) {
    return null
  }

  return messages[messages.length - 1]?.id ?? null
}

function ChatRoomListView({
  rooms,
  isLoading,
  errorMessage,
  onEnterRoom,
}: {
  rooms: ChatRoomListItem[]
  isLoading: boolean
  errorMessage: string | null
  onEnterRoom: (room: ChatRoomListItem) => void
}) {
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

                    {room.lastMessageType === 'IMAGE' && room.lastImageUrl ? (
                      <div className="h-16 w-16 shrink-0 overflow-hidden rounded-2xl bg-primary-100/40">
                        <img
                          src={room.lastImageUrl}
                          alt={`${room.designerUserId} 최근 이미지`}
                          className="h-full w-full object-cover"
                          draggable={false}
                        />
                      </div>
                    ) : null}
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

function ChatRoomView({
  roomId,
  designerUserId,
}: {
  roomId: number | string
  designerUserId: string | undefined
}) {
  const roomContext = readChatRoomContext()
  const roomKey = String(roomId)
  const [initialImageUrl, setInitialImageUrl] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isRoomReady, setIsRoomReady] = useState(false)
  const [sendErrorMessage, setSendErrorMessage] = useState<string | null>(null)

  const lastMessageIdRef = useRef<number | string | null>(null)
  const hasEnteredRoomRef = useRef(false)

  const messagesQuery = useChatMessagePolling({
    roomId,
    enabled: roomId != null,
    fetcher: async (nextRoomId) => {
      const response = await getChatMessages(nextRoomId, {
        afterId: hasEnteredRoomRef.current ? lastMessageIdRef.current : null,
      })

      return {
        done: false,
        data: response.messages,
        message: response.message,
      }
    },
  })

  const sendMessageMutation = useMutation({
    mutationFn: async () => {
      return sendChatMessage({
        roomId,
        messageText: inputValue.trim(),
      })
    },
    onSuccess: (response) => {
      setInputValue('')
      setSendErrorMessage(null)

      const createdMessage = response.chatMessage
      if (!createdMessage) {
        return
      }

      setMessages((current) => {
        const exists = current.some(
          (message) => String(message.id) === String(createdMessage.id),
        )

        if (exists) {
          return current
        }

        const nextMessages = [...current, createdMessage]
        lastMessageIdRef.current = getLastMessageId(nextMessages)
        return nextMessages
      })
    },
    onError: (error) => {
      setSendErrorMessage(
        error instanceof Error ? error.message : '메시지 전송에 실패했습니다.',
      )
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

  useEffect(() => {
    if (roomKey === '') {
      setInitialImageUrl(null)
    }

    setMessages([])
    setInputValue('')
    setIsRoomReady(false)
    setSendErrorMessage(null)
    lastMessageIdRef.current = null
    hasEnteredRoomRef.current = false
  }, [roomKey])

  useEffect(() => {
    const incomingMessages = messagesQuery.data

    if (!incomingMessages) {
      return
    }

    setMessages((current) => {
      if (!hasEnteredRoomRef.current) {
        hasEnteredRoomRef.current = true
        setIsRoomReady(true)
        lastMessageIdRef.current = getLastMessageId(incomingMessages)
        return incomingMessages
      }

      if (incomingMessages.length === 0) {
        return current
      }

      const seen = new Set(current.map((message) => String(message.id)))
      const nextMessages = [...current]

      for (const nextMessage of incomingMessages) {
        if (seen.has(String(nextMessage.id))) {
          continue
        }

        nextMessages.push(nextMessage)
      }

      lastMessageIdRef.current = getLastMessageId(nextMessages)
      return nextMessages
    })
  }, [messagesQuery.data])

  const isSendDisabled =
    !isRoomReady || inputValue.trim() === '' || sendMessageMutation.isPending

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
            첫 입장 후에는 마지막 메시지 id 기준으로 after_id 폴링을 진행합니다.
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

          {messagesQuery.isPolling && !messages.length ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-sub">
              <LoaderCircle className="size-4 animate-spin" />
              메시지를 불러오고 있습니다.
            </div>
          ) : null}

          {messages.map((message) => (
            <ChatMessageBubble
              key={String(message.id)}
              align={message.senderUserId === designerUserId ? 'left' : 'right'}
              text={message.messageText}
              imageUrl={
                message.messageType === 'IMAGE' ? message.imageUrl : null
              }
            />
          ))}

          {!initialImageUrl && !messages.length ? (
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
          <div className="flex items-end gap-3">
            <textarea
              value={inputValue}
              onChange={(event) => {
                setInputValue(event.target.value)
                if (sendErrorMessage) {
                  setSendErrorMessage(null)
                }
              }}
              placeholder="메시지를 입력하세요"
              rows={2}
              className="min-h-[52px] flex-1 resize-none rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm text-text-dark outline-none transition focus:border-primary-250"
              disabled={!isRoomReady}
            />

            <Button
              type="button"
              variant="login"
              size="icon"
              className="size-12 shrink-0 rounded-2xl"
              onClick={() => {
                void sendMessageMutation.mutateAsync()
              }}
              disabled={isSendDisabled}
              aria-label="메시지 전송"
            >
              {sendMessageMutation.isPending ? (
                <LoaderCircle className="size-5 animate-spin" />
              ) : (
                <SendHorizonal className="size-5" />
              )}
            </Button>
          </div>

          {sendErrorMessage ? (
            <p className="mt-2 text-sm text-error" role="alert">
              {sendErrorMessage}
            </p>
          ) : !isRoomReady ? (
            <p className="mt-2 text-sm text-text-sub">
              채팅방을 준비하는 중입니다. 잠시만 기다려 주세요.
            </p>
          ) : null}
        </section>
      </div>
    </main>
  )
}

export default function Chat() {
  const navigate = useNavigate()
  const search = useSearch({ from: '/chat' })
  const roomContext = readChatRoomContext()
  const roomId = search.roomId ?? roomContext?.roomId ?? null
  const designerUserId = search.designerUserId ?? roomContext?.designerUserId

  const chatRoomsQuery = useQuery({
    queryKey: ['chatRooms'],
    queryFn: getChatRooms,
    enabled: roomId == null,
  })

  if (roomId != null) {
    return (
      <ChatRoomView
        roomId={roomId}
        designerUserId={designerUserId ?? undefined}
      />
    )
  }

  return (
    <ChatRoomListView
      rooms={chatRoomsQuery.data?.rooms ?? []}
      isLoading={chatRoomsQuery.isLoading}
      errorMessage={
        chatRoomsQuery.error instanceof Error
          ? chatRoomsQuery.error.message
          : null
      }
      onEnterRoom={(room) => {
        void navigate({
          to: '/chat',
          search: {
            roomId: String(room.roomId),
            designerUserId: room.designerUserId,
          },
        })
      }}
    />
  )
}
