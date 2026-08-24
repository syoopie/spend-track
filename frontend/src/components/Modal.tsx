import { useEffect, useId, useRef, type ReactNode } from 'react'

const FOCUSABLE_SELECTOR =
  'input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'

// X-1 in UI Review.dc.html: before this, Modal had none of the behaviour a
// dialog is expected to have - no Escape to close, no focus trap, no
// initial focus, no focus restore on close, no role="dialog"/aria-modal,
// no scroll lock, and no close button on several callers (only the
// backdrop click, which is also the easiest way to dismiss a half-filled
// form by accident). Every one of those is handled here once, generically,
// rather than per caller.
export function Modal({
  onClose,
  children,
  width = 440,
  title,
}: {
  onClose: () => void
  children: ReactNode
  width?: number
  // ReactNode, not string - some callers need a styled title (the danger-
  // red heading on a destructive-action modal), not just plain text.
  title?: ReactNode
}) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const titleId = useId()
  // Captured during RENDER, not inside the effect below - several callers
  // put `autoFocus` on their first field, and React applies a native
  // autoFocus attribute synchronously during commit, which happens BEFORE
  // any useEffect runs. Capturing document.activeElement inside the effect
  // meant it had already been stolen by the child's own autoFocus by the
  // time this ran, so "restore focus on close" was restoring focus to the
  // modal's own first field instead of the button that opened it. A
  // plain (non-lazy) useRef argument is only used for the very first
  // render, which happens before this component's children ever commit -
  // safely ahead of any native autoFocus.
  const previouslyFocusedRef = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  // Kept fresh every render without being an effect dependency - onClose is
  // an inline arrow function at nearly every call site, so a new reference
  // on every parent re-render. If the setup/cleanup effect below depended
  // on it directly, the effect would re-run on every such re-render, not
  // just on actual open/close.
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    // Captured as a variable here (not read as previouslyFocusedRef.current
    // directly in the cleanup below) purely to satisfy static analysis of
    // "a ref read in a cleanup may have changed by the time it runs" - this
    // ref's .current is set exactly once, during render, and never
    // reassigned anywhere else, so there's nothing to go stale in practice.
    const previouslyFocused = previouslyFocusedRef.current

    const container = dialogRef.current
    // Searched within the body first, not the whole dialog - the header's
    // own close button is the first focusable element in DOM order once a
    // `title` is set, and would otherwise win over a caller's actual first
    // field every time. Falls back to the close button/dialog surface only
    // for a body with nothing focusable in it at all.
    const firstFocusable = bodyRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
      ?? container?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR)
    ;(firstFocusable ?? container)?.focus()

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab' || !container) return
      const focusables = [...container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)]
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
      // Wraps Tab/Shift+Tab at the dialog's edges so focus can never
      // escape to the page underneath while it's open.
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = originalOverflow
      previouslyFocused?.focus?.()
    }
    // Deliberately empty - see onCloseRef above. This must run exactly once
    // on mount and once on unmount, not on every onClose identity change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div onClick={onClose} className="fixed inset-0 bg-black/55 z-50 flex items-center justify-center">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-2xl p-6.5 outline-none"
        style={{ width }}
      >
        {title && (
          <div className="flex items-center justify-between gap-4 mb-4">
            <div id={titleId} className="text-base font-bold">
              {title}
            </div>
            <button
              onClick={onClose}
              aria-label="Close"
              className="shrink-0 text-muted hover:text-text text-lg leading-none cursor-pointer border-none bg-transparent"
            >
              ×
            </button>
          </div>
        )}
        <div ref={bodyRef}>{children}</div>
      </div>
    </div>
  )
}
