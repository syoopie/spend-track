import { useState } from 'react'
import { useVersion } from '../api/hooks'

// Dismissal is keyed on the version it dismissed, not a boolean, so the
// banner comes back for the *next* release rather than being silenced for
// good by one click.
const STORAGE_KEY = 'spendtrack-update-dismissed'

function loadDismissedVersion(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function UpdateAvailableNotice() {
  const { data } = useVersion()
  const [dismissed, setDismissed] = useState(loadDismissedVersion)

  const latest = data?.latest
  if (!data?.update_available || !latest || latest === dismissed) return null

  function dismiss() {
    if (!latest) return
    try {
      localStorage.setItem(STORAGE_KEY, latest)
    } catch {
      // localStorage unavailable (private mode, etc.) - the dismissal still
      // works for this session, it just won't survive a reload.
    }
    setDismissed(latest)
  }

  return (
    <div
      className="shrink-0 flex items-center justify-between gap-4 px-5 py-2 text-xs"
      style={{ background: 'var(--color-warning-surface)', color: 'var(--color-warning-text)' }}
    >
      <span>
        SpendTrack {latest} is available. You&apos;re on {data.current}.{' '}
        <a
          href={data.release_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-inherit font-semibold underline underline-offset-2"
        >
          Download
        </a>
      </span>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="shrink-0 bg-transparent border-none cursor-pointer text-inherit opacity-70 hover:opacity-100"
      >
        ×
      </button>
    </div>
  )
}
