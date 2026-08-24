import { forwardRef, type HTMLAttributes } from 'react'

// The "bg-card border border-border rounded-xl p-5" wrapper repeated across
// every settings/summary card in the app (root cause 01 in
// docs/ui-conventions.md). `padding` covers the few call sites that used a
// tighter p-4.5 instead of the default p-5. forwardRef exists solely so a
// caller can scroll a specific card into view (Dashboard.tsx's feed card,
// the target of DASH-5's "scroll the feed into view on click").
export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement> & { padding?: string }>(
  function Card({ padding = 'p-5', className = '', ...rest }, ref) {
    return <div ref={ref} className={`bg-card border border-border rounded-xl ${padding} ${className}`} {...rest} />
  },
)
