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

export type ChatRoomListItem = {
  roomId: number | string
  designerUserId: string
  lastMessageType: 'TEXT' | 'IMAGE' | null
  lastMessageText: string | null
  lastImageUrl: string | null
  updatedAt: string | null
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

export type ChatRoomsResponse = {
  code: number
  message: string
  rooms: ChatRoomListItem[]
}

export type GetChatMessagesOptions = {
  afterId?: number | string | null
}

export type SendChatMessageRequest = {
  roomId: number | string
  messageText: string
}

export type SendChatMessageResponse = {
  code: number
  message: string
  chatMessage: ChatMessage | null
}

type RawCreateChatRoomResponse = Partial<{
  code: number
  message: string
  roomId: number | string
  room_id: number | string
  chatRoomId: number | string
  chat_room_id: number | string
}>

type RawChatRoom = Partial<{
  roomId: number | string
  room_id: number | string
  id: number | string
  designerUserId: string
  designer_user_id: string
  partnerUserId: string
  partner_user_id: string
  otherUserId: string
  other_user_id: string
  userId: string
  user_id: string
  lastMessageType: 'TEXT' | 'IMAGE'
  last_message_type: 'TEXT' | 'IMAGE'
  lastMessageText: string | null
  last_message_text: string | null
  lastImageUrl: string | null
  last_image_url: string | null
  updatedAt: string
  updated_at: string
}>

type RawChatMessage = Partial<{
  id: number | string
  messageId: number | string
  senderUserId: string
  sender_user_id: string
  messageType: 'TEXT' | 'IMAGE'
  message_type: 'TEXT' | 'IMAGE'
  messageText: string | null
  message_text: string | null
  imageUrl: string | null
  image_url: string | null
  createdAt: string
  created_at: string
}>

type RawChatRoomsResponse = Partial<{
  code: number
  message: string
  rooms: RawChatRoom[]
  chatRooms: RawChatRoom[]
  roomList: RawChatRoom[]
  data:
    | RawChatRoom[]
    | Partial<{
        rooms: RawChatRoom[]
        chatRooms: RawChatRoom[]
        roomList: RawChatRoom[]
      }>
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

type RawSendChatMessageResponse = Partial<{
  code: number
  message: string
  chatMessage: RawChatMessage
  messageData: RawChatMessage
  data: RawChatMessage
}>

let chatRoomDraft: ChatRoomDraft | null = null
let chatRoomContext: ChatRoomContext | null = null

function normalizeChatRoom(room: RawChatRoom, index: number): ChatRoomListItem {
  return {
    roomId: room.roomId ?? room.room_id ?? room.id ?? `room-${index + 1}`,
    designerUserId:
      room.designerUserId ??
      room.designer_user_id ??
      room.partnerUserId ??
      room.partner_user_id ??
      room.otherUserId ??
      room.other_user_id ??
      room.userId ??
      room.user_id ??
      `디자이너 ${index + 1}`,
    lastMessageType: room.lastMessageType ?? room.last_message_type ?? null,
    lastMessageText: room.lastMessageText ?? room.last_message_text ?? null,
    lastImageUrl: room.lastImageUrl ?? room.last_image_url ?? null,
    updatedAt: room.updatedAt ?? room.updated_at ?? null,
  }
}

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

function extractRooms(data: RawChatRoomsResponse | null): ChatRoomListItem[] {
  const list =
    data?.rooms ??
    data?.chatRooms ??
    data?.roomList ??
    (Array.isArray(data?.data)
      ? data.data
      : (data?.data?.rooms ?? data?.data?.chatRooms ?? data?.data?.roomList)) ??
    []

  if (!Array.isArray(list)) {
    return []
  }

  return list.map(normalizeChatRoom)
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

function extractSingleMessage(
  data: RawSendChatMessageResponse | null,
): ChatMessage | null {
  const message = data?.chatMessage ?? data?.messageData ?? data?.data ?? null

  if (!message || typeof message !== 'object') {
    return null
  }

  return normalizeChatMessage(message, 0)
}

export async function getChatRooms(): Promise<ChatRoomsResponse> {
  const response = await apiFetch('/chat/rooms/', {
    method: 'GET',
  })

  const data = (await response
    .json()
    .catch(() => null)) as RawChatRoomsResponse | null

  if (!response.ok) {
    throw new Error(data?.message ?? '채팅방 목록을 불러오지 못했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '조회 정상',
    rooms: extractRooms(data),
  }
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
  options?: GetChatMessagesOptions,
): Promise<ChatMessagesResponse> {
  const params = new URLSearchParams()

  if (options?.afterId != null && `${options.afterId}` !== '') {
    params.set('after_id', String(options.afterId))
  }

  const query = params.toString()
  const path = query
    ? `/chat/rooms/${roomId}/messages/?${query}`
    : `/chat/rooms/${roomId}/messages/`

  const response = await apiFetch(path, {
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

export async function sendChatMessage({
  roomId,
  messageText,
}: SendChatMessageRequest): Promise<SendChatMessageResponse> {
  const response = await apiFetch(`/chat/rooms/${roomId}/messages/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message_text: messageText,
    }),
  })

  const data = (await response
    .json()
    .catch(() => null)) as RawSendChatMessageResponse | null

  if (!response.ok) {
    throw new Error(data?.message ?? '메시지 전송에 실패했습니다.')
  }

  return {
    code: data?.code ?? 200,
    message: data?.message ?? '메시지를 전송했습니다.',
    chatMessage: extractSingleMessage(data),
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

export function clearChatRoomContext() {
  chatRoomContext = null
}
