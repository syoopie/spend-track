import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

// The "px-9 pt-7 pb-15" + "text-title font-bold font-display" page-header
// pair was already consistent by convention across every page but hand
// re-typed on each one (root cause 01). Settings and Guide opt into a
// maxWidth; Guide also opts into the leading icon tile, which is why that's
// a prop here rather than a reason to hand-roll a second header shape.
export function PageShell({
  title,
  subtitle,
  icon: Icon,
  actions,
  maxWidth = '',
  children,
}: {
  title: string
  subtitle?: ReactNode
  icon?: LucideIcon
  actions?: ReactNode
  maxWidth?: string
  children: ReactNode
}) {
  return (
    <div className={`px-9 pt-7 pb-15 ${maxWidth}`}>
      <div className="flex items-start justify-between gap-4 mb-5">
        <div className="flex items-center gap-3 min-w-0">
          {Icon && (
            <div className="w-10 h-10 rounded-xl bg-accent/12 flex items-center justify-center shrink-0">
              <Icon size={18} className="text-accent" />
            </div>
          )}
          <div className="min-w-0">
            <div className="text-title font-bold font-display">{title}</div>
            {subtitle && <div className="text-md text-muted mt-1">{subtitle}</div>}
          </div>
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
