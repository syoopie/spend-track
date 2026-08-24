import { useEffect, useState } from 'react'

// X-9 in UI Review.dc.html: nothing in the app has a breakpoint, and the
// feed grid / four-across metric row / 860px dialogs all assume a wide
// window - below ~1100px, columns start colliding rather than wrapping.
// Rather than adding md: breakpoints across every screen (a much larger,
// higher-risk change touching most of the app's layout), this states the
// minimum supported width explicitly and surfaces it instead of letting the
// layout break silently, per the doc's own accepted alternative.
const MIN_WIDTH = 1280

function isNarrow() {
  return typeof window !== 'undefined' && window.innerWidth < MIN_WIDTH
}

export function NarrowWindowNotice() {
  const [narrow, setNarrow] = useState(isNarrow)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    function onResize() {
      setNarrow(isNarrow())
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  if (!narrow || dismissed) return null

  return (
    <div
      className="shrink-0 flex items-center justify-between gap-4 px-5 py-2 text-xs"
      style={{ background: 'var(--color-warning-surface)', color: 'var(--color-warning-text)' }}
    >
      <span>This app is designed for windows at least {MIN_WIDTH}px wide — layout may look cramped or overlap below that.</span>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss"
        className="shrink-0 bg-transparent border-none cursor-pointer text-inherit opacity-70 hover:opacity-100"
      >
        ×
      </button>
    </div>
  )
}
