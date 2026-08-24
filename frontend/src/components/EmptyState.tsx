import { AlertTriangle, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './Button'

// Only the no-accounts Dashboard had a designed empty state before this;
// every other list screen fell back to one muted line in a bordered box
// (X-4 in UI Review.dc.html). Matches that Dashboard state's visual shape -
// accent-tinted icon square, headline, one line of explanation, optional
// primary action - so adopting it elsewhere doesn't introduce a second look.
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center text-center py-14 px-6">
      <div className="w-11 h-11 rounded-xl bg-accent/12 mb-4 flex items-center justify-center">
        <Icon size={20} className="text-accent" />
      </div>
      <div className="text-md font-semibold text-text mb-1.5">{title}</div>
      {description && <div className="text-xs text-muted max-w-xs mb-4">{description}</div>}
      {action}
    </div>
  )
}

// Companion to EmptyState for isError - so "no data" and "the backend is
// down" stop rendering as the same blank box (root cause 04 / X-4).
export function ErrorState({
  title = 'Something went wrong',
  description = "Couldn't load this. Check your connection and try again.",
  onRetry,
}: {
  title?: string
  description?: string
  onRetry?: () => void
}) {
  return (
    <div className="flex flex-col items-center text-center py-14 px-6">
      <div
        className="w-11 h-11 rounded-xl mb-4 flex items-center justify-center"
        style={{ background: 'var(--color-danger-badge-bg)' }}
      >
        <AlertTriangle size={20} style={{ color: 'var(--color-danger-badge-fg)' }} />
      </div>
      <div className="text-md font-semibold text-text mb-1.5">{title}</div>
      <div className="text-xs text-muted max-w-xs mb-4">{description}</div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
