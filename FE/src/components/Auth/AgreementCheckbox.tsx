type Props = {
  id?: string
  checked: boolean
  onChange: (checked: boolean) => void
  onBlur?: () => void
}

export function AgreementCheckbox({ id, checked, onChange, onBlur }: Props) {
  return (
    <input
      id={id}
      type="checkbox"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
      onBlur={onBlur}
      className="h-5 w-5 rounded border border-gray-300 accent-primary-300"
    />
  )
}
