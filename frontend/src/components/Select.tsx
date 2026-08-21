import { ChevronDown } from 'lucide-react'
import { Children, isValidElement, useEffect, useRef, useState } from 'react'
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
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onPointerDown)
    return () => window.removeEventListener('mousedown', onPointerDown)
  }, [open])

  useEffect(() => {
    if (open) listRef.current?.querySelector<HTMLElement>('[data-active="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [open, activeIndex])

  function openAt(index: number) {
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
      {open && (
        <div
          ref={listRef}
          role="listbox"
          className="absolute left-0 top-[calc(100%+4px)] z-40 min-w-full w-max max-w-[320px] max-h-64 overflow-y-auto bg-card border border-border rounded-lg shadow-xl py-1"
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
        </div>
      )}
    </div>
  )
}
