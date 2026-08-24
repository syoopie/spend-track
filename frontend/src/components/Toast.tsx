import { CheckCircle2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

export interface ToastMessage {
  kind: 'success' | 'error'
  text: string
}

// A single transient corner notification, not a queue/stack - nothing in
// the app fires more than one of these at a time yet, so a newer toast just
// replaces whatever's currently showing (the caller owns the timer that
// clears it back to null - see Settings.tsx's AiSection).
export function Toast({ toast }: { toast: ToastMessage | null }) {
  const [entered, setEntered] = useState(false)

  useEffect(() => {
    if (!toast) return
    setEntered(false)
    const id = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(id)
  }, [toast])

  if (!toast) return null

  return (
    <div className="fixed bottom-6 right-6 z-[100] pointer-events-none">
      <div
        className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border text-md shadow-lg transition-[opacity,transform] duration-200 ${
          entered ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
        }`}
        style={
          toast.kind === 'success'
            ? { background: 'var(--color-success-surface)', borderColor: 'var(--color-success-surface-border)', color: 'var(--color-success-text)' }
            : { background: 'var(--color-warning-surface)', borderColor: 'var(--color-warning-surface-border)', color: 'var(--color-warning-text)' }
        }
      >
        {toast.kind === 'success' ? (
          <CheckCircle2 size={15} className="shrink-0" />
        ) : (
          <XCircle size={15} className="shrink-0" />
        )}
        {toast.text}
      </div>
    </div>
  )
}
