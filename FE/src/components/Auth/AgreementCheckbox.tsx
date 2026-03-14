import { Check } from 'lucide-react'

type AgreementCheckboxProps = {
  checked: boolean
  onChange: (checked: boolean) => void
  onBlur?: () => void
  label: string
  requiredText?: string
  id?: string
  disabled?: boolean
}

export function AgreementCheckbox({
  checked,
  onChange,
  onBlur,
  label,
  requiredText,
  id = 'agreement-checkbox',
  disabled = false,
}: AgreementCheckboxProps) {
  return (
    <label
      htmlFor={id}
      className={`flex items-center gap-2.5 ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      }`}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        onBlur={onBlur}
        className="peer sr-only"
      />

      <span
        className="
          flex h-6 w-6 shrink-0 items-center justify-center
          rounded-[10px] border-2
          border-[#C9CDD3] bg-white
          transition-all duration-200
          peer-checked:border-[#D98296] peer-checked:bg-[#D98296]
          peer-focus-visible:ring-2 peer-focus-visible:ring-[#E8B6C2] peer-focus-visible:ring-offset-1
        "
      >
        <Check
          className={`h-4 w-4 text-white transition-all duration-200 ${
            checked ? 'scale-100 opacity-100' : 'scale-75 opacity-0'
          }`}
          strokeWidth={3}
        />
      </span>

      <span className="text-[14px] font-semibold tracking-[-0.01em] text-slate-700">
        <span className="mr-1 text-[#E08A97]">{requiredText}</span>
        {label}
      </span>
    </label>
  )
}
