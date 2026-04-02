import type * as React from 'react'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { cn } from '@/lib/utils'

type BottomSheetProps = {
  isOpen: boolean
  onClose: () => void
  title?: string
  ariaLabel?: string
  children?: React.ReactNode
  className?: string
  overlayClassName?: string
  portalToAppFrame?: boolean
}

export function BottomSheet({
  isOpen,
  onClose,
  title,
  ariaLabel,
  children,
  className,
  overlayClassName,
  portalToAppFrame = false,
}: BottomSheetProps) {
  const [portalContainer, setPortalContainer] = useState<Element | null>(null)

  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  useEffect(() => {
    if (!portalToAppFrame) {
      setPortalContainer(null)
      return
    }

    setPortalContainer(document.querySelector('.app-frame'))
  }, [portalToAppFrame])

  if (!isOpen) return null

  const content = (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel ?? title}
      className="absolute inset-0 z-50 flex items-end justify-center"
    >
      <div
        className={cn('absolute inset-0 bg-black/50', overlayClassName)}
        onClick={onClose}
        aria-hidden="true"
      />

      <div
        className={cn(
          'relative z-10 mt-auto w-full rounded-t-[28px] bg-white px-4 pb-[calc(2rem+env(safe-area-inset-bottom))] pt-3 shadow-[0_-18px_48px_rgba(15,23,42,0.24)]',
          className,
        )}
      >
        {title && (
          <h2 className="mb-4 text-base font-semibold text-text-dark">
            {title}
          </h2>
        )}

        {children}
      </div>
    </div>
  )

  if (portalToAppFrame && portalContainer) {
    return createPortal(content, portalContainer)
  }

  return content
}

export type { BottomSheetProps }
