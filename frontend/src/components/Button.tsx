import { forwardRef, type ButtonHTMLAttributes } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'danger-outline' | 'ghost'
export type ButtonSize = 'md' | 'sm'

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'font-semibold border-none bg-accent text-accent-fg hover:bg-accent-hover',
  secondary: 'border border-border bg-input text-text hover:border-accent/50',
  danger: 'font-semibold border-none bg-danger text-danger-fg hover:opacity-90',
  'danger-outline':
    'font-semibold bg-input border border-[var(--color-danger-border)] text-[var(--color-danger-text)]',
  ghost: 'border-none bg-transparent text-muted hover:text-text',
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  md: 'text-md px-4 py-2.5',
  sm: 'text-xs px-3.5 py-2',
}

// The one button implementation for every "form action" call site (modal
// Cancel/Confirm pairs, card actions, etc). Root cause 01 in
// docs/ui-conventions.md - this used to be restyled by hand at ~40 call
// sites in five near-identical variants. Bespoke controls that aren't really
// "a button with a label" (Select's trigger, Tabs, calendar day cells,
// Sidebar nav items) are deliberately left as their own components.
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
}>(function Button({ variant = 'secondary', size = 'md', className = '', type = 'button', ...rest }, ref) {
  return (
    <button
      ref={ref}
      type={type}
      className={`rounded-lg cursor-pointer transition-colors disabled:opacity-50 disabled:cursor-not-allowed
        focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2
        ${SIZE_CLASSES[size]} ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  )
})
