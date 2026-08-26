import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * True once the nearest scrolling ancestor of the attached element has been
 * scrolled away from its top.
 *
 * Exists because a scroll shadow is only meaningful while something is
 * actually passing underneath: a `shadow-[0_4px_6px_-4px_...]` drawn
 * unconditionally paints ~6px of shadow onto whatever sits directly below
 * the sticky element at rest, and since a sticky header's own bottom padding
 * is *inside* its box, that is the card immediately below it - which reads
 * as the header overlapping the card rather than as depth.
 *
 * Returns a *callback* ref rather than taking an object ref, because the
 * headers that want this generally render only after their page's first data
 * arrives (the Dashboard renders a loading sentence on its first pass). An
 * effect keyed on `[]` would run against `ref.current === null` and never
 * subscribe; a callback ref fires whenever the node actually attaches.
 */
export function useScrolledUnder<T extends HTMLElement>(): [boolean, (node: T | null) => void] {
  const [scrolled, setScrolled] = useState(false)
  const detach = useRef<(() => void) | null>(null)

  const attach = useCallback((node: T | null) => {
    detach.current?.()
    detach.current = null
    if (!node) return

    let scroller: HTMLElement | null = node.parentElement
    while (scroller) {
      const overflowY = getComputedStyle(scroller).overflowY
      if (overflowY === 'auto' || overflowY === 'scroll') break
      scroller = scroller.parentElement
    }

    // Every sticky header in this app sits inside an explicit scroll pane
    // (App.tsx's page scroller, the feed's own bounded list, a dialog's row
    // list), but fall back to the document so a future caller outside one
    // still gets the right answer rather than a shadow stuck on.
    const target: HTMLElement | Window = scroller ?? window
    const read = () =>
      setScrolled((scroller ? scroller.scrollTop : document.documentElement.scrollTop) > 0)
    read()
    target.addEventListener('scroll', read, { passive: true })
    detach.current = () => target.removeEventListener('scroll', read)
  }, [])

  useEffect(() => () => detach.current?.(), [])

  return [scrolled, attach]
}
