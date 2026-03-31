import { cn } from '@/lib/utils'

type ChatMessageBubbleProps = {
  align?: 'left' | 'right'
  text?: string | null
  imageUrl?: string | null
  caption?: string | null
}

export function ChatMessageBubble({
  align = 'left',
  text,
  imageUrl,
  caption,
}: ChatMessageBubbleProps) {
  const isRight = align === 'right'

  return (
    <div className={cn('flex', isRight ? 'justify-end' : 'justify-start')}>
      <div className="max-w-[78%]">
        {imageUrl ? (
          <div
            className={cn(
              'overflow-hidden rounded-[24px] shadow-[0_18px_36px_rgba(15,23,42,0.08)]',
              isRight ? 'rounded-br-md' : 'rounded-bl-md',
            )}
          >
            <img
              src={imageUrl}
              alt={caption ?? '채팅 이미지'}
              className="h-auto w-full object-cover"
              draggable={false}
            />
          </div>
        ) : null}

        {text ? (
          <div
            className={cn(
              'rounded-[24px] px-4 py-3 text-sm leading-6 shadow-[0_12px_24px_rgba(15,23,42,0.08)]',
              isRight
                ? 'rounded-br-md bg-primary-300 text-white'
                : 'rounded-bl-md bg-white text-text-dark',
              imageUrl ? 'mt-2' : undefined,
            )}
          >
            {text}
          </div>
        ) : null}

        {caption && imageUrl ? (
          <p
            className={cn(
              'mt-2 text-xs font-medium text-text-sub',
              isRight ? 'text-right' : 'text-left',
            )}
          >
            {caption}
          </p>
        ) : null}
      </div>
    </div>
  )
}
