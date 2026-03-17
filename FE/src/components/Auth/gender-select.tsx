import { ChevronDown } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

export type Gender = '' | 'M' | 'F'

type GenderSelectProps = {
  value: Gender
  onChange: (value: Gender) => void
  onBlur?: () => void
  error?: boolean
}

const OPTIONS: Array<{ value: Gender; label: string }> = [
  { value: '', label: '선택안함' },
  { value: 'M', label: '남성' },
  { value: 'F', label: '여성' },
]

export function GenderSelect({
  value,
  onChange,
  onBlur,
  error = false,
}: GenderSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement | null>(null)

  const selectedLabel =
    OPTIONS.find((option) => option.value === value)?.label ?? '미선택'

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!rootRef.current) return
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  function handleSelect(nextValue: Gender) {
    onChange(nextValue)
    setOpen(false)
    onBlur?.()
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
        onBlur={() => {
          onBlur?.()
        }}
        className={`flex h-12 w-full items-center justify-between rounded-2xl border bg-white px-4 text-base outline-none transition ${
          error
            ? 'border-red-400 focus:border-red-400'
            : 'border-gray-200 focus:border-primary-200'
        }`}
      >
        <span className={value ? 'text-slate-700' : 'text-slate-400'}>
          {selectedLabel}
        </span>
        <ChevronDown
          className={`h-5 w-5 text-gray-400 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute z-20 w-full overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-lg"
        >
          {OPTIONS.map((option) => {
            const isSelected = option.value === value

            return (
              <li key={option.value} role="option" aria-selected={isSelected}>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleSelect(option.value)}
                  className={`w-full px-4 py-3 text-left text-base transition ${
                    isSelected
                      ? 'bg-primary-50 font-semibold text-primary-300'
                      : 'text-slate-700 hover:bg-gray-50'
                  }`}
                >
                  {option.label}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}