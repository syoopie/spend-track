import type { HTMLAttributes } from 'react'

// The "bg-card border border-border rounded-xl p-5" wrapper repeated across
// every settings/summary card in the app (root cause 01 in
// docs/ui-conventions.md). `padding` covers the few call sites that used a
// tighter p-4.5 instead of the default p-5.
export function Card({
  padding = 'p-5',
  className = '',
  ...rest
}: HTMLAttributes<HTMLDivElement> & { padding?: string }) {
  return <div className={`bg-card border border-border rounded-xl ${padding} ${className}`} {...rest} />
}
