import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'

import { ChatRoomListView } from '@/components/chat-room-list-view'
import { ChatRoomView } from '@/components/chat-room-view'
import { getChatRooms, readChatRoomContext } from '@/lib/chat'

export default function Chat() {
  const navigate = useNavigate()
  const search = useSearch({ from: '/chat' })
  const roomContext = readChatRoomContext()
  const roomId = search.roomId ?? null
  const designerUserId =
    search.designerUserId ??
    (roomId != null ? roomContext?.designerUserId : null)

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
