import { useCallback, useContext } from 'react'
import { UndoableDeleteContext } from '../components/UndoableDeleteProvider'

/**
 * The app's one delete gesture: hide the row immediately, show a toast with
 * Undo, and only send the real DELETE once the undo window closes.
 *
 * Rules and the transaction feed each carried their own byte-identical copy
 * of this - one of them with a comment saying a shared constant wasn't worth
 * it "since the two screens have no other coupling". Contacts made three,
 * which is where a retyped shape becomes a primitive (root cause 01 in
 * docs/ui-conventions.md). The state and timers live in
 * UndoableDeleteProvider, above the router, so the gesture survives leaving
 * (or returning to) the page mid-window.
 *
 * `mutate` is the delete mutation's own `.mutate`; it still runs, and still
 * invalidates its query cache, when called after the calling page has
 * unmounted (that side effect is on `useMutation`, not on this `mutate`
 * call - see TanStack Query's "mutation callbacks and component unmounting").
 */
export function useUndoableDelete(
  noun: string,
  mutate: (id: number, options: { onError: () => void }) => void,
) {
  const ctx = useContext(UndoableDeleteContext)
  const requestDelete = useCallback(
    (id: number, label: string) => ctx!.requestDelete(noun, id, label, mutate),
    [ctx, noun, mutate],
  )
  if (!ctx) throw new Error('useUndoableDelete must be used within UndoableDeleteProvider')
  return { pendingIds: ctx.pendingFor(noun), requestDelete }
}
