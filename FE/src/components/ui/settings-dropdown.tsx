import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

type ModalSelectOption = {
  value: string
  label: string
}

type ModalSelectProps = {
  id?: string
  value: string
  options: ModalSelectOption[]
  onChange: (value: string) => void
}

export function ModalSelect({
  id,
  value,
  options,
  onChange,
}: ModalSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  const selectedOption =
    options.find((option) => option.value === value) ?? options[0]

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!rootRef.current) return
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  return (
    <div ref={rootRef} className="relative">
      <button
        id={id}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => {
          setOpen((prev) => !prev)
        }}
        className="flex h-12 w-full items-center justify-between rounded-2xl border border-white/15 bg-white/10 px-4 text-left text-sm font-medium text-white outline-none transition hover:bg-white/[0.12] focus:border-white/35"
      >
        <span>{selectedOption?.label}</span>
        <ChevronDown
          className={[
            'h-4 w-4 text-white/65 transition',
            open ? 'rotate-180' : '',
          ].join(' ')}
        />
      </button>

      {open ? (
        <div className="absolute left-0 right-0 top-[calc(100%+8px)] z-50 overflow-hidden rounded-2xl border border-white/10 bg-black/85 shadow-2xl backdrop-blur-md">
          <div role="listbox" aria-labelledby={id} className="py-2">
            {options.map((option) => {
              const selected = option.value === value

              return (
                <div key={option.value}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={selected}
                    onClick={() => {
                      onChange(option.value)
                      setOpen(false)
                    }}
                    className={[
                      'flex w-full items-center justify-between px-4 py-3 text-sm transition',
                      selected
                        ? 'bg-white/12 text-white'
                        : 'text-white/80 hover:bg-white/8 hover:text-white',
                    ].join(' ')}
                  >
                    <span>{option.label}</span>
                    {selected ? <Check className="h-4 w-4" /> : null}
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
