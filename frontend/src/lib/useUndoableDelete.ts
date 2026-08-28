import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '../components/Toast'

// How long a deleted row stays hidden-but-recoverable before the delete
// actually reaches the backend (X-2 in UI Review.dc.html) - matches the
// toast's own duration so the undo option and the row's disappearance stay
// in sync.
export const DELETE_UNDO_MS = 6000

/**
 * The app's one delete gesture: hide the row immediately, show a toast with
 * Undo, and only send the real DELETE once the undo window closes.
 *
 * Rules and the transaction feed each carried their own byte-identical copy
 * of this - one of them with a comment saying a shared constant wasn't worth
 * it "since the two screens have no other coupling". Contacts made three,
 * which is where a retyped shape becomes a primitive (root cause 01 in
 * docs/ui-conventions.md).
 *
 * `pendingIds` is deliberately state of its own rather than an optimistic
 * write into the query cache: Rules composes its reorder payload from the
 * cached list, and the backend rejects a reorder that doesn't name every
 * non-default rule - including ones hidden here but not yet deleted.
 */
export function useUndoableDelete(
  noun: string,
  mutate: (id: number, options: { onError: () => void }) => void,
) {
  const toast = useToast()
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set())
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>())

  useEffect(() => {
    const pending = timers
    return () => {
      for (const t of pending.current.values()) clearTimeout(t)
    }
  }, [])

  const unhide = useCallback((id: number) => {
    setPendingIds((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }, [])

  const requestDelete = useCallback(
    (id: number, label: string) => {
      setPendingIds((prev) => new Set(prev).add(id))
      const timer = setTimeout(() => {
        timers.current.delete(id)
        // The optimistic removal turned out to be wrong - un-hide the row
        // rather than lose it silently (the mutation's own onError already
        // toasts the failure).
        mutate(id, { onError: () => unhide(id) })
      }, DELETE_UNDO_MS)
      timers.current.set(id, timer)
      toast.success(`${noun} deleted — "${label}"`, {
        durationMs: DELETE_UNDO_MS,
        action: {
          label: 'Undo',
          onClick: () => {
            clearTimeout(timers.current.get(id))
            timers.current.delete(id)
            unhide(id)
          },
        },
      })
    },
    [mutate, noun, toast, unhide],
  )

  return { pendingIds, requestDelete }
}
