import { useMutation } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { DesignerListCard } from '@/components/designer-list-card'
import { Header } from '@/components/header'
import {
  type DesignerListItem,
  readDesignerListCache,
} from '@/lib/Camera/designer'
import {
  clearChatRoomDraft,
  createChatRoom,
  readChatRoomDraft,
} from '@/lib/chat'

export default function DesignerList() {
  const navigate = useNavigate()
  const designers = readDesignerListCache()
  const [requestMessage, setRequestMessage] = useState<string | null>(null)

  const chatRoomMutation = useMutation({
    mutationFn: async (designer: DesignerListItem) => {
      const draft = readChatRoomDraft()
      if (!draft) {
        throw new Error('전송할 적용 이미지가 없습니다.')
      }

      return createChatRoom({
        designerUserId: designer.name,
        hairId: draft.hairId,
        appliedImage: draft.appliedImage,
      })
    },
  })

  async function handleRequestDesigner(designer: DesignerListItem) {
    setRequestMessage(null)

    try {
      const response = await chatRoomMutation.mutateAsync(designer)
      clearChatRoomDraft()

      await navigate({
        to: '/chat',
        search: {
          roomId: String(response.roomId),
          designerUserId: designer.name,
        },
      })
    } catch (caught) {
      setRequestMessage(
        caught instanceof Error
          ? caught.message
          : '채팅방 생성에 실패했습니다.',
      )
    }
  }

  return (
    <main className="app-frame-page h-full overflow-y-auto bg-bg-primary pb-[108px]">
      <div className="mx-auto flex w-full max-w-[390px] flex-col px-4 pt-3">
        <Header label="디자이너" className="px-0 pb-3 pt-2" />

        {requestMessage ? (
          <div className="mb-4 rounded-2xl bg-card px-4 py-3 text-sm text-error">
            {requestMessage}
          </div>
        ) : null}

        <section className="mt-5 flex flex-col gap-4 pb-6">
          {designers.length > 0 ? (
            designers.map((designer, index) => (
              <DesignerListCard
                key={`${designer.id}-${designer.name}`}
                designer={designer}
                rank={index + 1}
                requestPending={chatRoomMutation.isPending}
                onRequest={handleRequestDesigner}
              />
            ))
          ) : (
            <div className="rounded-[28px] bg-card px-5 py-10 text-center shadow-[0_18px_36px_rgba(15,23,42,0.08)]">
              <p className="text-base font-semibold text-text-dark">
                불러온 디자이너 정보가 없습니다.
              </p>
              <p className="mt-2 text-sm leading-6 text-text-sub">
                카메라 화면에서 다시 디자이너 찾기를 시도해주세요.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
