import { Check } from 'lucide-react'

export function Checkbox({
  checked,
  onChange,
  className = '',
  disabled = false,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  className?: string
  disabled?: boolean
}) {
  return (
    <span className={`relative inline-flex w-4 h-4 shrink-0 items-center justify-center ${className}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="peer appearance-none m-0 w-4 h-4 rounded-sm border border-border bg-input cursor-pointer
          transition-colors hover:border-accent checked:bg-accent checked:border-accent
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <Check
        size={11}
        strokeWidth={3}
        className="pointer-events-none absolute opacity-0 peer-checked:opacity-100 text-accent-fg"
      />
    </span>
  )
}
