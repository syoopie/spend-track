import type { ReactNode } from 'react'

// The "px-9 pt-7 pb-15" + "text-title font-bold font-display" page-header
// pair was already consistent by convention across every page but hand
// re-typed on each one (root cause 01). Settings is the one page that opts
// into a narrower maxWidth - see SET-2 in UI Review.dc.html, not yet fixed.
export function PageShell({
  title,
  subtitle,
  actions,
  maxWidth = '',
  children,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
  maxWidth?: string
  children: ReactNode
}) {
  return (
    <div className={`px-9 pt-7 pb-15 ${maxWidth}`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div>
          <div className="text-title font-bold font-display">{title}</div>
          {subtitle && <div className="text-md text-muted mt-1">{subtitle}</div>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
