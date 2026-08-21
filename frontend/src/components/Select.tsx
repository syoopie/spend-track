import { ChevronDown } from 'lucide-react'
import type { SelectHTMLAttributes } from 'react'

export function Select({
  className = '',
  uiSize = 'md',
  bg = 'input',
  children,
  ...props
}: Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> & { uiSize?: 'sm' | 'md'; bg?: 'input' | 'card' }) {
  const padding = uiSize === 'sm' ? 'pl-2.5 pr-7 py-1.5 text-[13px]' : 'pl-3 pr-8 py-2 text-[13px]'
  const bgClass = bg === 'card' ? 'bg-card' : 'bg-input'
  return (
    <span className={`relative inline-block ${className}`}>
      <select
        {...props}
        className={`w-full appearance-none ${padding} ${bgClass} rounded-lg border border-border text-text cursor-pointer
          transition-colors hover:border-accent
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {children}
      </select>
      <ChevronDown
        size={uiSize === 'sm' ? 12 : 14}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-2"
      />
    </span>
  )
}
