import { apiFetch } from '@/lib/api'

const CHAT_REQUEST_DRAFT_STORAGE_KEY = 'chat-request-draft'

export type ChatRoomDraft = {
  hairId: number
  appliedImageDataUrl: string
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

type RawCreateChatRoomResponse = Partial<{
  code: number
  message: string
  roomId: number | string
  room_id: number | string
  chatRoomId: number | string
  chat_room_id: number | string
}>

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

export function writeChatRoomDraft(draft: ChatRoomDraft) {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.setItem(
    CHAT_REQUEST_DRAFT_STORAGE_KEY,
    JSON.stringify(draft),
  )
}

export function readChatRoomDraft(): ChatRoomDraft | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.sessionStorage.getItem(CHAT_REQUEST_DRAFT_STORAGE_KEY)
    if (!raw) {
      return null
    }

    return JSON.parse(raw) as ChatRoomDraft
  } catch {
    return null
  }
}

export function clearChatRoomDraft() {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.removeItem(CHAT_REQUEST_DRAFT_STORAGE_KEY)
}

export async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const response = await fetch(dataUrl)
  return response.blob()
}
