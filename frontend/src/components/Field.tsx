import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

// The "w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input
// text-text text-md" string was copy-pasted at ~15 call sites (root cause 01
// in docs/ui-conventions.md). `mono` covers the handful of inputs that also
// added font-mono by hand (paths, DELETE-to-confirm fields, rule patterns).
// `fullWidth=false` (the rare narrower field - a search box, a priority
// number) drops the w-full class entirely rather than letting a caller pass
// a conflicting width utility through className: two width utilities in one
// class list both target the `width` property, and which one wins depends
// on Tailwind's generated stylesheet order, not on string position - not
// safe to rely on.
export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & { mono?: boolean; fullWidth?: boolean }
>(function Input({ className = '', mono = false, fullWidth = true, ...rest }, ref) {
  return (
    <input
      ref={ref}
      className={`${fullWidth ? 'w-full' : ''} box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-md
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2
        ${mono ? 'font-mono' : ''} ${className}`}
      {...rest}
    />
  )
})

// Pairs a label (and optional hint line) with its control - matches the
// "text-xs text-muted mb-1" label + input pattern already used across
// Settings/Rules/Contacts, now shared instead of hand-repeated.
export function Field({
  label,
  hint,
  children,
  className = '',
}: {
  label?: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      {label && <div className="text-xs text-muted mb-1">{label}</div>}
      {children}
      {hint && <div className="text-2xs text-muted-2 mt-1">{hint}</div>}
    </div>
  )
}
