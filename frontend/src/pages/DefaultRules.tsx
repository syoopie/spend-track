import { ChevronDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useCategories, useRules } from '../api/hooks'
import { categoryColor, categoryIcon } from '../lib/categoryColor'
import type { Rule } from '../api/types'

function CategoryGroup({
  category,
  rules,
  defaultOpen,
}: {
  category: string
  rules: Rule[]
  defaultOpen: boolean
}) {
  const categoriesQ = useCategories()
  const [manualOpen, setManualOpen] = useState<boolean | null>(null)
  const open = manualOpen ?? defaultOpen
  const cc = categoryColor(categoriesQ.data, category)
  const Icon = categoryIcon(categoriesQ.data, category)

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setManualOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-[13px] font-semibold border-none bg-transparent cursor-pointer text-text"
      >
        <span className="flex items-center gap-2">
          <Icon size={14} color={cc.fg} className="shrink-0" />
          {category}
          <span className="text-muted-2 font-normal text-xs">({rules.length})</span>
        </span>
        <ChevronDown size={16} className={`text-muted-2 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-border/70">
          {rules.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between gap-3 px-5 py-2.5 text-[13px] border-b border-border/70 last:border-b-0"
            >
              <span className="font-semibold">{r.display_label ?? r.match_pattern}</span>
              <span className="text-muted-2 text-xs">
                matches <span className="font-mono bg-input px-1.5 py-0.5 rounded">{r.match_pattern}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function DefaultRules() {
  const rulesQ = useRules(true)
  const [search, setSearch] = useState('')

  const groups = useMemo(() => {
    const all = (rulesQ.data ?? []).filter((r) => r.is_default)
    const q = search.trim().toUpperCase()
    const filtered = q
      ? all.filter(
          (r) =>
            r.match_pattern.toUpperCase().includes(q) ||
            (r.display_label ?? '').toUpperCase().includes(q) ||
            (r.target_category ?? '').toUpperCase().includes(q),
        )
      : all

    const byCategory = new Map<string, Rule[]>()
    for (const r of filtered) {
      const key = r.target_category ?? ''
      if (!byCategory.has(key)) byCategory.set(key, [])
      byCategory.get(key)!.push(r)
    }
    for (const rules of byCategory.values()) {
      rules.sort((a, b) => a.match_pattern.localeCompare(b.match_pattern))
    }
    return [...byCategory.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [rulesQ.data, search])

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="text-[22px] font-bold font-display">Default Categorization Rules</div>
          <div className="text-[13px] text-muted mt-0.5">
            Built-in word bank used to auto-categorize transactions — read-only, and always evaluated after your own
            rules so anything you set up takes precedence
          </div>
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search merchant or category…"
          className="text-[13px] px-3 py-2 rounded-lg border border-border bg-input text-text w-[240px]"
        />
      </div>

      {rulesQ.isLoading && <div className="text-muted text-sm">Loading…</div>}
      {!rulesQ.isLoading && groups.length === 0 && (
        <div className="text-muted text-sm">No default rules match "{search}".</div>
      )}
      <div className="flex flex-col gap-3">
        {groups.map(([category, rules]) => (
          <CategoryGroup key={category} category={category} rules={rules} defaultOpen={!!search} />
        ))}
      </div>
    </div>
  )
}
