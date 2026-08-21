import { ChevronDown } from 'lucide-react'
import { Children, isValidElement, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { KeyboardEvent as ReactKeyboardEvent, OptionHTMLAttributes, ReactNode } from 'react'

interface SelectOption {
  value: string
  label: ReactNode
  disabled?: boolean
}

export function Select({
  value,
  onChange,
  children,
  className = '',
  uiSize = 'md',
  bg = 'input',
  disabled = false,
}: {
  value: string
  onChange: (e: { target: { value: string } }) => void
  children: ReactNode
  className?: string
  uiSize?: 'sm' | 'md'
  bg?: 'input' | 'card'
  disabled?: boolean
}) {
  // A native <select>'s trigger can be themed, but its open options popup is
  // rendered by the OS and ignores page CSS entirely - that mismatch (a
  // dark-themed app popping a stark white native listbox) is what this
  // component exists to avoid. <option> children are still accepted so call
  // sites don't change; they're parsed for {value, label} and rendered as a
  // fully-styled panel instead of a real <select>.
  const options: SelectOption[] = Children.toArray(children)
    .filter(isValidElement)
    .map((child) => {
      const optProps = child.props as OptionHTMLAttributes<HTMLOptionElement>
      return { value: String(optProps.value ?? ''), label: optProps.children, disabled: optProps.disabled }
    })

  const [open, setOpen] = useState(false)
  // Focus deliberately never leaves the trigger button while the panel is
  // open (same model a native <select> uses) - arrow keys move this instead
  // of DOM focus. That's what lets Escape/Tab/selecting an option all just
  // work without any explicit "return focus to the trigger" step.
  const [activeIndex, setActiveIndex] = useState(0)
  // The panel is portaled to <body> (see render below) so it can't be
  // clipped by an overflow-hidden ancestor (e.g. the Transaction Feed card
  // when the feed is short/empty) - position is computed from the
  // trigger's viewport rect instead of relying on CSS `absolute`.
  const [panelStyle, setPanelStyle] = useState({ top: 0, left: 0, minWidth: 0 })
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node
      // The panel is portaled to <body>, so it's not a DOM descendant of
      // containerRef - it needs its own exemption or every option click
      // would close (and unmount) the panel on mousedown, before the
      // option button's own click handler ever fires.
      if (containerRef.current?.contains(target)) return
      if (listRef.current?.contains(target)) return
      setOpen(false)
    }
    window.addEventListener('mousedown', onPointerDown)
    // Closing on scroll (rather than repositioning) matches how most
    // portaled dropdowns behave and avoids the panel drifting out of sync
    // with a trigger that scrolled off inside a nested scroll container.
    // Capture-phase scroll fires for every ancestor up to window regardless
    // of the target's own bubbling, so the panel's own internal
    // overflow-y-auto scroll needs an explicit exemption or scrolling the
    // option list would immediately close it.
    function onScroll(e: Event) {
      if (listRef.current && listRef.current.contains(e.target as Node)) return
      setOpen(false)
    }
    window.addEventListener('scroll', onScroll, true)
    return () => {
      window.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('scroll', onScroll, true)
    }
  }, [open])

  useEffect(() => {
    if (open) listRef.current?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex])

  function openAt(index: number) {
    const rect = triggerRef.current?.getBoundingClientRect()
    if (rect) {
      const panelMaxHeight = 256 // matches max-h-64 below
      const openUpward = window.innerHeight - rect.bottom < panelMaxHeight && rect.top > panelMaxHeight
      setPanelStyle({
        top: openUpward ? rect.top - panelMaxHeight - 4 : rect.bottom + 4,
        left: rect.left,
        minWidth: rect.width,
      })
    }
    setActiveIndex(Math.max(0, Math.min(options.length - 1, index)))
    setOpen(true)
  }

  function commit(index: number) {
    const opt = options[index]
    if (!opt || opt.disabled) return
    onChange({ target: { value: opt.value } })
    setOpen(false)
  }

  function handleKeyDown(e: ReactKeyboardEvent<HTMLButtonElement>) {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        const currentIdx = options.findIndex((o) => o.value === value)
        openAt(currentIdx >= 0 ? currentIdx : 0)
      }
      return
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setActiveIndex((i) => Math.min(options.length - 1, i + 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setActiveIndex((i) => Math.max(0, i - 1))
        break
      case 'Home':
        e.preventDefault()
        setActiveIndex(0)
        break
      case 'End':
        e.preventDefault()
        setActiveIndex(options.length - 1)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        commit(activeIndex)
        break
      case 'Escape':
        e.preventDefault()
        setOpen(false)
        break
      case 'Tab':
        setOpen(false)
        break
    }
  }

  const selected = options.find((o) => o.value === value)
  const padding = uiSize === 'sm' ? 'pl-2.5 pr-7 py-1.5 text-[13px]' : 'pl-3 pr-8 py-2 text-[13px]'
  const bgClass = bg === 'card' ? 'bg-card' : 'bg-input'

  return (
    <div className={`relative inline-block ${className}`} ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openAt(options.findIndex((o) => o.value === value)))}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={open}
        className={`w-full flex items-center gap-1.5 text-left appearance-none ${padding} ${bgClass} rounded-lg border border-border text-text cursor-pointer
          transition-colors hover:border-accent
          focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2
          disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <span className="truncate min-w-0">{selected?.label ?? value}</span>
      </button>
      <ChevronDown
        size={uiSize === 'sm' ? 12 : 14}
        className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-2"
      />
      {open &&
        createPortal(
          <div
            ref={listRef}
            role="listbox"
            style={{ position: 'fixed', top: panelStyle.top, left: panelStyle.left, minWidth: panelStyle.minWidth }}
            className="z-50 w-max max-w-[320px] max-h-64 overflow-y-auto bg-card border border-border rounded-lg shadow-xl py-1"
          >
            {options.map((o, i) => (
              <button
                key={o.value}
                type="button"
                role="option"
                tabIndex={-1}
                aria-selected={o.value === value}
                data-active={i === activeIndex}
                disabled={o.disabled}
                onMouseEnter={() => setActiveIndex(i)}
                onClick={() => commit(i)}
                className={`w-full flex items-center gap-1.5 text-left px-3 py-1.5 text-[13px] whitespace-nowrap cursor-pointer border-0 bg-transparent
                  disabled:opacity-40 disabled:cursor-not-allowed
                  ${i === activeIndex ? 'bg-accent/12' : ''}
                  ${o.value === value ? 'text-accent font-semibold' : 'text-text'}`}
              >
                {o.label}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  )
}
