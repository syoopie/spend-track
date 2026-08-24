import type { ReactNode } from 'react'

export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  right,
}: {
  tabs: { key: T; label: string }[]
  active: T
  onChange: (key: T) => void
  // A qualifier for the active tab's content (e.g. "recent trend") - lives
  // here instead of as a second heading inside the tab's own panel, which is
  // what caused DASH-3's literal title duplication ("Cash Flow" tab, "Cash
  // Flow — Recent Trend" panel heading right below it).
  right?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-3 mb-3.5 border-b border-border">
      <div className="flex gap-1">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => onChange(t.key)}
            className={`text-xs font-semibold px-3 py-2 -mb-px border-0 border-b-2 bg-transparent cursor-pointer transition-colors ${
              active === t.key ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {right && <div className="text-2xs text-muted-2 shrink-0 pr-0.5">{right}</div>}
    </div>
  )
}
