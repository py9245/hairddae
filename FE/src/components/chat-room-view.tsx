import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { ChevronLeft, LoaderCircle, SendHorizonal } from 'lucide-react'
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'

import { ChatMessageBubble } from '@/components/chat-message-bubble'
import { Header } from '@/components/header'
import { Button } from '@/components/ui/button'
import { useChatMessagePolling } from '@/hooks/Chat/use-chat-message-polling'
import {
  type ChatMessage,
  clearChatRoomContext,
  getChatMessages,
  readChatRoomContext,
  sendChatMessage,
} from '@/lib/chat'

function getLastMessageId(messages: ChatMessage[]) {
  if (messages.length === 0) {
    return null
  }

  return messages[messages.length - 1]?.id ?? null
}

type ChatRoomViewProps = {
  roomId: number | string
  designerUserId: string | undefined
}

export function ChatRoomView({ roomId, designerUserId }: ChatRoomViewProps) {
  const navigate = useNavigate()
  const roomContext = readChatRoomContext()
  const roomKey = String(roomId)
  const [initialImageUrl, setInitialImageUrl] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isRoomReady, setIsRoomReady] = useState(false)
  const [sendErrorMessage, setSendErrorMessage] = useState<string | null>(null)

  const lastMessageIdRef = useRef<number | string | null>(null)
  const hasEnteredRoomRef = useRef(false)
  const messageViewportRef = useRef<HTMLDivElement | null>(null)
  const messageContentRef = useRef<HTMLDivElement | null>(null)

  const scrollToBottom = useCallback(() => {
    const viewport = messageViewportRef.current
    if (!viewport) {
      return
    }

    viewport.scrollTop = viewport.scrollHeight
  }, [])

  const fetchChatMessages = useCallback(async (nextRoomId: number | string) => {
    const response = await getChatMessages(nextRoomId, {
      afterId: hasEnteredRoomRef.current ? lastMessageIdRef.current : null,
    })

    return {
      done: false,
      data: response.messages,
      message: response.message,
    }
  }, [])

  const messagesQuery = useChatMessagePolling({
    roomId,
    enabled: roomId != null,
    fetcher: fetchChatMessages,
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
    setMessages([])
    setInputValue('')
    setIsRoomReady(false)
    setSendErrorMessage(null)
    lastMessageIdRef.current = null
    hasEnteredRoomRef.current = false

    if (roomKey === '') {
      setInitialImageUrl(null)
    }
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

  const messageCount = messages.length

  useLayoutEffect(() => {
    if (!initialImageUrl && messageCount === 0 && !messagesQuery.isPolling) {
      return
    }

    scrollToBottom()

    const frame1 = window.requestAnimationFrame(scrollToBottom)
    const frame2 = window.requestAnimationFrame(scrollToBottom)
    const timeoutId = window.setTimeout(scrollToBottom, 120)

    return () => {
      window.cancelAnimationFrame(frame1)
      window.cancelAnimationFrame(frame2)
      window.clearTimeout(timeoutId)
    }
  }, [initialImageUrl, messageCount, messagesQuery.isPolling, scrollToBottom])

  useEffect(() => {
    const content = messageContentRef.current
    if (!content || typeof ResizeObserver === 'undefined') {
      return
    }

    const observer = new ResizeObserver(() => {
      scrollToBottom()
    })

    observer.observe(content)

    return () => {
      observer.disconnect()
    }
  }, [scrollToBottom])

  const isSendDisabled =
    !isRoomReady || inputValue.trim() === '' || sendMessageMutation.isPending

  return (
    <main className="app-frame-page relative h-full overflow-hidden bg-[#f5f1f2]">
      <Header
        className="border-b border-black/5 bg-white/92 px-4 py-3 backdrop-blur"
        leftAction={
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="채팅 목록으로 이동"
            className="border-0 bg-transparent shadow-none hover:bg-transparent"
            onClick={() => {
              clearChatRoomContext()
              void navigate({
                to: '/chat',
                search: {},
              })
            }}
          >
            <ChevronLeft className="size-5" />
          </Button>
        }
        centerContent={
          <div className="text-center">
            <p className="text-base font-bold text-text-dark">
              {designerUserId ?? '디자이너'}
            </p>
          </div>
        }
      />

      <div className="mx-auto flex h-full w-full max-w-[390px] flex-col pt-[76px]">
        <section
          ref={messageViewportRef}
          className="min-h-0 flex-1 overflow-y-auto px-4 py-5 pb-[110px]"
        >
          {initialImageUrl || messages.length > 0 || messagesQuery.isPolling ? (
            <div
              ref={messageContentRef}
              className="flex min-h-full flex-col justify-end gap-4"
            >
              {messagesQuery.isPolling && !messages.length ? (
                <div className="flex items-center justify-center gap-2 py-10 text-sm text-text-sub">
                  <LoaderCircle className="size-4 animate-spin" />
                  메시지를 불러오고 있습니다.
                </div>
              ) : null}

              {messages.map((message) => (
                <ChatMessageBubble
                  key={String(message.id)}
                  align={
                    message.senderUserId === designerUserId ? 'left' : 'right'
                  }
                  text={message.messageText}
                  imageUrl={
                    message.messageType === 'IMAGE' ? message.imageUrl : null
                  }
                />
              ))}

              {messagesQuery.isError ? (
                <div className="flex justify-center pt-2">
                  <p
                    className="rounded-full bg-white px-4 py-2 text-sm text-error shadow-[0_8px_20px_rgba(15,23,42,0.08)]"
                    role="alert"
                  >
                    {messagesQuery.message ??
                      '채팅 메시지를 불러오지 못했습니다.'}
                  </p>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-end px-8 pb-8 text-center">
              <div className="rounded-full bg-white px-4 py-2 text-xs font-semibold tracking-[0.16em] text-primary-300 uppercase shadow-[0_10px_20px_rgba(15,23,42,0.06)]">
                New Conversation
              </div>
              <p className="mt-4 text-lg font-bold text-text-dark">
                아직 주고받은 메시지가 없습니다.
              </p>
              <p className="mt-2 text-sm leading-6 text-text-sub">
                아래 입력창에서 바로 상담 메시지를 보내실 수 있습니다.
              </p>
            </div>
          )}
        </section>

        <section className="absolute right-0 bottom-0 left-0 px-4 pb-4 pt-3">
          <div className="mx-auto w-full max-w-[390px]">
            <div className="flex items-center gap-3 rounded-[28px] border border-black/6 bg-white px-3 py-2 shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
              <textarea
                value={inputValue}
                onChange={(event) => {
                  setInputValue(event.target.value)
                  if (sendErrorMessage) {
                    setSendErrorMessage(null)
                  }
                }}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' || event.shiftKey) {
                    return
                  }

                  event.preventDefault()

                  if (isSendDisabled) {
                    return
                  }

                  void sendMessageMutation.mutateAsync()
                }}
                placeholder="메시지를 입력하세요."
                rows={1}
                className="max-h-28 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-5 text-text-dark outline-none placeholder:text-text-sub"
                disabled={!isRoomReady}
              />

              <Button
                type="button"
                variant="login"
                size="icon"
                className="size-11 shrink-0 rounded-2xl"
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
                채팅방을 준비하고 있습니다. 잠시만 기다려 주세요.
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </main>
  )
}
