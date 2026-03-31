import { apiFetch } from '@/lib/api'

export type ChatRoomDraft = {
  hairId: number
  appliedImage: Blob
}

export type ChatRoomContext = {
  roomId: number | string
  designerUserId: string
  appliedImage: Blob | null
}

export type CreateChatRoomRequest = {
  designerUserId: string
  hairId: number
  appliedImage: Blob
  initialMessage?: string
}

export type CreateChatRoomResponse = {
  code: number
  message: string
  roomId: number | string
}

export type ChatMessage = {
  id: number | string
  senderUserId: string
  messageType: 'TEXT' | 'IMAGE'
  messageText: string | null
  imageUrl: string | null
  createdAt: string | null
}

export type ChatMessagesResponse = {
  code: number
  message: string
  roomId: number | string
  messages: ChatMessage[]
}

type RawCreateChatRoomResponse = Partial<{
  code: number
  message: string
  roomId: number | string
  room_id: number | string
  chatRoomId: number | string
  chat_room_id: number | string
}>

type RawChatMessage = Partial<{
  id: number | string
  messageId: number | string
  senderUserId: string
  sender_user_id: string
  messageType: 'TEXT' | 'IMAGE'
  message_type: 'TEXT' | 'IMAGE'
  messageText: string
  message_text: string
  imageUrl: string
  image_url: string
  createdAt: string
  created_at: string
}>

type RawChatMessagesResponse = Partial<{
  code: number
  message: string
  roomId: number | string
  room_id: number | string
  messages: RawChatMessage[]
  chatMessages: RawChatMessage[]
  messageList: RawChatMessage[]
  data:
    | RawChatMessage[]
    | Partial<{
        messages: RawChatMessage[]
        chatMessages: RawChatMessage[]
        messageList: RawChatMessage[]
      }>
}>

let chatRoomDraft: ChatRoomDraft | null = null
let chatRoomContext: ChatRoomContext | null = null

function normalizeChatMessage(
  message: RawChatMessage,
  index: number,
): ChatMessage {
  return {
    id: message.id ?? message.messageId ?? `message-${index + 1}`,
    senderUserId: message.senderUserId ?? message.sender_user_id ?? '',
    messageType:
      message.messageType ??
      message.message_type ??
      (message.imageUrl || message.image_url ? 'IMAGE' : 'TEXT'),
    messageText: message.messageText ?? message.message_text ?? null,
    imageUrl: message.imageUrl ?? message.image_url ?? null,
    createdAt: message.createdAt ?? message.created_at ?? null,
  }
}

function extractMessages(data: RawChatMessagesResponse | null): ChatMessage[] {
  const list =
    data?.messages ??
    data?.chatMessages ??
    data?.messageList ??
    (Array.isArray(data?.data)
      ? data.data
      : (data?.data?.messages ??
        data?.data?.chatMessages ??
        data?.data?.messageList)) ??
    []

  if (!Array.isArray(list)) {
    return []
  }

  return list.map(normalizeChatMessage)
}

export async function createChatRoom({
  designerUserId,
  hairId,
  appliedImage,
  initialMessage,
}: CreateChatRoomRequest): Promise<CreateChatRoomResponse> {
  const formData = new FormData()
  formData.append('designer_user_id', designerUserId)
  formData.append('hair_id', String(hairId))
  formData.append('applied_image', appliedImage, 'applied-image.png')

  if (initialMessage && initialMessage.trim() !== '') {
    formData.append('initial_message', initialMessage.trim())
  }

  const response = await apiFetch('/chat/rooms/', {
    method: 'POST',
    body: formData,
  })

  const data = (await response
    .json()
    .catch(() => null)) as RawCreateChatRoomResponse | null

  if (!response.ok) {
    throw new Error(data?.message ?? '채팅방 생성에 실패했습니다.')
  }

  const roomId =
    data?.roomId ?? data?.room_id ?? data?.chatRoomId ?? data?.chat_room_id

  if (roomId == null) {
    throw new Error('채팅방 ID를 받지 못했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '채팅방이 생성되었습니다.',
    roomId,
  }
}

export async function getChatMessages(
  roomId: number | string,
): Promise<ChatMessagesResponse> {
  const response = await apiFetch(`/chat/rooms/${roomId}/messages/`, {
    method: 'GET',
  })

  const data = (await response
    .json()
    .catch(() => null)) as RawChatMessagesResponse | null

  if (!response.ok) {
    throw new Error(data?.message ?? '채팅 메시지를 불러오지 못했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '조회 정상',
    roomId: data?.roomId ?? data?.room_id ?? roomId,
    messages: extractMessages(data),
  }
}

export function writeChatRoomDraft(draft: ChatRoomDraft) {
  chatRoomDraft = draft
}

export function readChatRoomDraft(): ChatRoomDraft | null {
  return chatRoomDraft
}

export function clearChatRoomDraft() {
  chatRoomDraft = null
}

export function writeChatRoomContext(context: ChatRoomContext) {
  chatRoomContext = context
}

export function readChatRoomContext(): ChatRoomContext | null {
  return chatRoomContext
}
