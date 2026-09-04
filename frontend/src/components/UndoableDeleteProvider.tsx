import { createContext, useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { useToast } from './Toast'

// How long a deleted row stays hidden-but-recoverable before the delete
// actually reaches the backend (X-2 in UI Review.dc.html) - matches the
// toast's own duration so the undo option and the row's disappearance stay
// in sync.
const DELETE_UNDO_MS = 6000

type Commit = (id: number, options: { onError: () => void }) => void

export interface UndoableDeleteContextValue {
  pendingFor: (noun: string) => Set<number>
  requestDelete: (noun: string, id: number, label: string, commit: Commit) => void
}

export const UndoableDeleteContext = createContext<UndoableDeleteContextValue | null>(null)

const EMPTY = new Set<number>()

/**
 * Owns the app's one row-delete gesture for every screen with a list: hide
 * the row immediately, toast with an Undo action, and send the real DELETE
 * only once the 6s window closes.
 *
 * It sits above the router on purpose. A pending delete and the toast that
 * offers to undo it both outlive the page the row was on, so leaving that
 * page mid-window neither drops the delete (the timer used to be cleared on
 * unmount) nor un-hides the row on the way back (the hidden set used to be
 * page state that reset on remount). The toast is already app-level and
 * keeps its Undo button working across the navigation.
 *
 * The hidden set is kept here rather than written optimistically into the
 * query cache because Rules builds its reorder payload from the cached list
 * and the backend rejects a reorder that omits a rule - including one hidden
 * here but not yet deleted.
 */
export function UndoableDeleteProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  // noun -> ids currently hidden pending their delete. Keyed by noun so two
  // screens' ids can't collide and so touching one screen's set leaves the
  // others' references (and their memoised list filters) untouched.
  const [pending, setPending] = useState<Record<string, Set<number>>>({})
  // No unmount cleanup for these timers, unlike the per-page hook this replaced:
  // the provider wraps the whole app and unmounts only on teardown, and a timer
  // outliving the page its row was on is the entire point.
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

  const forget = useCallback((noun: string, id: number) => {
    setPending((prev) => {
      const next = new Set(prev[noun])
      next.delete(id)
      return { ...prev, [noun]: next }
    })
  }, [])

  const requestDelete = useCallback<UndoableDeleteContextValue['requestDelete']>(
    (noun, id, label, commit) => {
      setPending((prev) => ({ ...prev, [noun]: new Set(prev[noun]).add(id) }))
      const key = `${noun}:${id}`
      timers.current.set(
        key,
        setTimeout(() => {
          timers.current.delete(key)
          // The optimistic removal turned out to be wrong - un-hide the row
          // rather than lose it silently (the mutation's own onError toasts
          // the failure).
          commit(id, { onError: () => forget(noun, id) })
        }, DELETE_UNDO_MS),
      )
      toast.success(`${noun} deleted — "${label}"`, {
        durationMs: DELETE_UNDO_MS,
        action: {
          label: 'Undo',
          onClick: () => {
            clearTimeout(timers.current.get(key))
            timers.current.delete(key)
            forget(noun, id)
          },
        },
      })
    },
    [toast, forget],
  )

  const value = useMemo<UndoableDeleteContextValue>(
    () => ({ pendingFor: (noun) => pending[noun] ?? EMPTY, requestDelete }),
    [pending, requestDelete],
  )

  return <UndoableDeleteContext.Provider value={value}>{children}</UndoableDeleteContext.Provider>
}
