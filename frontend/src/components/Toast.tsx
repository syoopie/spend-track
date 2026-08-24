import { CheckCircle2, XCircle } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'

export type ToastKind = 'success' | 'error'

interface QueuedToast {
  id: number
  kind: ToastKind
  text: string
}

interface ToastContextValue {
  success: (text: string) => void
  error: (text: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

// How long a toast stays up before auto-dismissing - success is a quick
// confirmation, error stays longer since it's more likely the user needs to
// actually read it (and possibly go fix something).
const SUCCESS_DURATION_MS = 3000
const ERROR_DURATION_MS = 6000

// A stacked queue mounted once in App, not a single slot owned by whichever
// component happens to fire it first (root cause 04 / X-3 in
// UI Review.dc.html: before this, Toast was rendered in exactly one place -
// the AI enable checkbox - and every other mutation in the app was either
// silent or left a stale inline message). api/hooks.ts calls useToast()
// from individual mutation hooks' onSuccess/onError, so a toast is a
// property of "this mutation succeeded/failed", not something each screen
// has to remember to wire up by hand.
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<QueuedToast[]>([])
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const show = useCallback(
    (kind: ToastKind, text: string) => {
      const id = nextId.current++
      setToasts((prev) => [...prev, { id, kind, text }])
      setTimeout(() => dismiss(id), kind === 'success' ? SUCCESS_DURATION_MS : ERROR_DURATION_MS)
    },
    [dismiss],
  )

  const value: ToastContextValue = {
    success: (text) => show('success', text),
    error: (text) => show('error', text),
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-6 right-6 z-[100] flex flex-col-reverse gap-2 pointer-events-none">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function ToastItem({ toast, onDismiss }: { toast: QueuedToast; onDismiss: () => void }) {
  const [entered, setEntered] = useState(false)
  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(id)
  }, [])

  return (
    <div
      role="status"
      onClick={onDismiss}
      className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-xl border text-md shadow-lg cursor-pointer transition-[opacity,transform] duration-200 ${
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
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
