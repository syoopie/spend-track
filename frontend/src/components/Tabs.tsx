export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string }[]
  active: T
  onChange: (key: T) => void
}) {
  return (
    <div className="flex gap-1 mb-3.5 border-b border-border">
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
  )
}
