import { useState } from 'react'
import { CalendarDays } from 'lucide-react'
import { Calendar } from '@/components/ui/calendar'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface Props {
  value: string
  onChange: (value: string) => void
  onBlur: () => void
  hasError: boolean
}

function toDate(value: string): Date | undefined {
  if (!value) return undefined
  const d = new Date(value)
  return isNaN(d.getTime()) ? undefined : d
}

function toISOString(date: Date): string {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function BirthDatePicker({ value, onChange, onBlur, hasError }: Props) {
  const [open, setOpen] = useState(false)
  const selected = toDate(value)

  const handleSelect = (date: Date | undefined) => {
    onChange(date ? toISOString(date) : '')
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          onBlur={onBlur}
          className={`h-12 w-full rounded-2xl border bg-input-surface px-4 text-left text-base outline-none flex items-center gap-2 ${
            hasError
              ? 'border-red-400 focus:border-red-400'
              : 'border-gray-200 focus:border-primary-200'
          }`}
        >
          <CalendarDays className="h-4 w-4 shrink-0 text-gray-400" />
          <span className={value ? 'text-slate-700' : 'text-sm text-gray-400'}>
            {value || '생년월일 선택'}
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0 rounded-2xl" align="start">
        <Calendar
          mode="single"
          selected={selected}
          onSelect={handleSelect}
          disabled={{ after: new Date() }}
          captionLayout="dropdown"
          defaultMonth={selected ?? new Date()}
          startMonth={new Date(1900, 0)}
          endMonth={new Date()}
        />
      </PopoverContent>
    </Popover>
  )
}
