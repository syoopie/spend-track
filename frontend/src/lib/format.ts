import { CURRENCY_SYMBOL } from './localization'

export function fmtSigned(n: number): string {
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n < 0 ? `-${CURRENCY_SYMBOL}` : `+${CURRENCY_SYMBOL}`) + abs
}

export function fmtPlain(n: number): string {
  const abs = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n < 0 ? `-${CURRENCY_SYMBOL}` : CURRENCY_SYMBOL) + abs
}

export function fmtDate(iso: string, opts?: { withYear?: boolean }): string {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString(
    'en-US',
    opts?.withYear ? { month: 'short', day: '2-digit', year: 'numeric' } : { month: 'short', day: '2-digit' },
  )
}

export function fmtMonthLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'short' })
}

export function shiftMonth(ym: string, delta: number): string {
  const [y, m] = ym.split('-').map(Number)
  const idx = y * 12 + (m - 1) + delta
  const y2 = Math.floor(idx / 12)
  const m2 = idx % 12
  return `${String(y2).padStart(4, '0')}-${String(m2 + 1).padStart(2, '0')}`
}

export function currentMonthKey(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function fmtMonthYearLabel(ym: string): string {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
}

export function fmtMonthRangeLabel(from: string, to: string): string {
  if (from === to) return fmtMonthYearLabel(from)
  const fromYear = from.slice(0, 4)
  const toYear = to.slice(0, 4)
  const toLabel = fromYear === toYear ? `${fmtMonthLabel(to)} ${toYear}` : fmtMonthYearLabel(to)
  return `${fmtMonthLabel(from)}${fromYear === toYear ? '' : ` ${fromYear}`} – ${toLabel}`
}

export function fmtCompact(n: number): string {
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 1000) return `${sign}${CURRENCY_SYMBOL}${(abs / 1000).toFixed(1)}K`
  return `${sign}${CURRENCY_SYMBOL}${abs.toFixed(0)}`
}

// "3 minutes ago" / "2 hours ago" / "5 days ago" - PendingReviewBanner
// (DASH-6 in UI Review.dc.html) needs to say how stale the pending batch is,
// not just that one exists. Coarse on purpose (minute/hour/day buckets only)
// since a pending statement is meant to be reviewed promptly, not tracked to
// the second.
export function fmtRelativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB']
  let value = bytes / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i++
  }
  return `${value.toFixed(1)} ${units[i]}`
}
