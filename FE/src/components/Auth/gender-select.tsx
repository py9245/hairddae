import { ChevronDown } from 'lucide-react'

export type Gender = '' | 'M' | 'F' | null

type Props = {
  value: Gender
  onChange: (value: Gender) => void
  onBlur?: () => void
}

export function GenderSelect({ value, onChange, onBlur }: Props) {
  return (
    <div>
      <label
        htmlFor="gender"
        className="mb-2 block text-base font-semibold text-slate-700"
      >
        성별 <span className="text-sm font-medium text-gray-400">(선택)</span>
      </label>
      <div className="relative">
        <select
          id="gender"
          value={value ?? ''}
          onChange={(e) => onChange((e.target.value || null) as Gender)}
          onBlur={onBlur}
          className="h-12 w-full appearance-none rounded-2xl border border-gray-200 bg-white px-4 text-base text-slate-700 outline-none focus:border-primary-200"
        >
          <option value="">선택안함</option>
          <option value="M">남성</option>
          <option value="F">여성</option>
        </select>
        <div className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">
          <ChevronDown />
        </div>
      </div>
    </div>
  )
}
