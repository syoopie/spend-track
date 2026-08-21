import { ChevronDown } from 'lucide-react'
import { Children, isValidElement, useEffect, useRef, useState } from 'react'
import type { OptionHTMLAttributes, ReactNode } from 'react'

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
  const containerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('mousedown', onPointerDown)
    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  useEffect(() => {
    if (open) listRef.current?.querySelector<HTMLElement>('[data-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [open])

  const selected = options.find((o) => o.value === value)
  const padding = uiSize === 'sm' ? 'pl-2.5 pr-7 py-1.5 text-[13px]' : 'pl-3 pr-8 py-2 text-[13px]'
  const bgClass = bg === 'card' ? 'bg-card' : 'bg-input'

  return (
    <div className={`relative inline-block ${className}`} ref={containerRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
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
          {options.map((o) => (
            <button
              key={o.value}
              type="button"
              role="option"
              aria-selected={o.value === value}
              data-selected={o.value === value}
              disabled={o.disabled}
              onClick={() => {
                onChange({ target: { value: o.value } })
                setOpen(false)
              }}
              className={`w-full flex items-center gap-1.5 text-left px-3 py-1.5 text-[13px] whitespace-nowrap cursor-pointer border-0 bg-transparent
                hover:bg-input disabled:opacity-40 disabled:cursor-not-allowed
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
