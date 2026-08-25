import { useEffect, useMemo, useState } from 'react'

// Shared by every place that shows "how long has the current AI pass been
// running" - ReviewDialog.tsx's in-dialog banner (with a Terminate action
// bolted on), PendingReviewBanner.tsx's staging banner, and Dashboard.tsx's
// Recategorize button. Previously only ReviewDialog had this logic; the
// other two needed the identical clock without the Terminate button, so it
// moved here rather than being copy-pasted a second and third time.
export function fmtElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

// Ticks off a fixed startedAt anchor (a setInterval re-rendering just the
// caller, not a whole dialog/page) rather than polling the server for it -
// the batch queries that carry ai_started_at already refresh every 1.5s
// while running, which is plenty to catch ai_status leaving "running", but
// far too coarse for a readable second-by-second clock.
export function useElapsedMs(startedAt: string): number {
  const startMs = useMemo(() => new Date(startedAt).getTime(), [startedAt])
  const [elapsedMs, setElapsedMs] = useState(() => Date.now() - startMs)
  useEffect(() => {
    setElapsedMs(Date.now() - startMs)
    const t = setInterval(() => setElapsedMs(Date.now() - startMs), 1000)
    return () => clearInterval(t)
  }, [startMs])
  return elapsedMs
}

export function ElapsedTimer({ startedAt, className }: { startedAt: string; className?: string }) {
  const elapsedMs = useElapsedMs(startedAt)
  return <span className={`font-mono ${className ?? ''}`}>{fmtElapsed(elapsedMs)}</span>
}
