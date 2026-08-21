export function Checkbox({
  checked,
  onChange,
  className = '',
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  className?: string
}) {
  return (
    <span className={`relative inline-flex w-4 h-4 shrink-0 items-center justify-center ${className}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer appearance-none m-0 w-4 h-4 rounded-[5px] border border-border bg-input cursor-pointer
          transition-colors hover:border-accent checked:bg-accent checked:border-accent
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
      />
      <svg
        className="pointer-events-none absolute w-2.5 h-2.5 opacity-0 peer-checked:opacity-100 text-accent-fg"
        viewBox="0 0 16 16"
        fill="none"
      >
        <path d="M3 8.5 L6.5 12 L13 4.5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  )
}
