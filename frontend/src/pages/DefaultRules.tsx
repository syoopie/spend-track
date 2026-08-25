import { ChevronDown, ListChecks, SearchX } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useCategories, useRules } from '../api/hooks'
import { categoryColor, categoryIcon } from '../lib/categoryColor'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { EmptyState, ErrorState } from '../components/EmptyState'
import { Input } from '../components/Field'
import { PageShell } from '../components/PageShell'
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
    <Card padding="" className="overflow-hidden">
      <button
        onClick={() => setManualOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-3.5 text-md font-semibold border-none bg-transparent cursor-pointer text-text"
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
              className="flex items-center justify-between gap-3 px-5 py-2.5 text-md border-b border-border/70 last:border-b-0"
            >
              <span className="font-semibold">{r.display_label ?? r.match_pattern}</span>
              <span className="text-muted-2 text-xs">
                matches <span className="font-mono bg-input px-1.5 py-0.5 rounded">{r.match_pattern}</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function DirectionSection({
  title,
  groups,
  defaultOpen,
}: {
  title: string
  groups: [string, Rule[]][]
  defaultOpen: boolean
}) {
  if (groups.length === 0) return null
  return (
    <div>
      <div className="text-2xs font-semibold text-muted-2 uppercase tracking-wide mb-2.5">{title}</div>
      <div className="flex flex-col gap-3">
        {groups.map(([category, rules]) => (
          <CategoryGroup key={category} category={category} rules={rules} defaultOpen={defaultOpen} />
        ))}
      </div>
    </div>
  )
}

export function DefaultRules() {
  const rulesQ = useRules(true)
  const categoriesQ = useCategories(true)
  const [search, setSearch] = useState('')

  const directionByCategory = useMemo(() => {
    const map = new Map<string, string>()
    for (const c of categoriesQ.data ?? []) map.set(c.name, c.direction)
    return map
  }, [categoriesQ.data])

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

  // Every category a default rule can target is direction-locked (see
  // api/types.ts's CategoryDirection) - splitting the page into these two
  // sections is what makes that split visible here, not just enforced
  // silently by the engine.
  const outflowGroups = groups.filter(([category]) => directionByCategory.get(category) !== 'inflow')
  const inflowGroups = groups.filter(([category]) => directionByCategory.get(category) === 'inflow')

  return (
    <PageShell
      title="Default Categorization Rules"
      subtitle="Built-in word bank used to auto-categorize transactions — read-only, and always evaluated after your own rules so anything you set up takes precedence"
      icon={ListChecks}
      actions={
        <Input
          fullWidth={false}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search merchant or category…"
          className="w-[240px]"
        />
      }
    >
      {rulesQ.isLoading && <div className="text-muted text-sm">Loading…</div>}
      {rulesQ.isError && <ErrorState description="Couldn't load the default rule bank." onRetry={() => rulesQ.refetch()} />}
      {rulesQ.isSuccess && groups.length === 0 && (
        <EmptyState
          icon={SearchX}
          title="No default rules match"
          description={`Nothing in the built-in word bank matches "${search}".`}
          action={
            <Button variant="secondary" size="sm" onClick={() => setSearch('')}>
              Clear search
            </Button>
          }
        />
      )}
      <div className="grid grid-cols-2 gap-5 items-start">
        <DirectionSection title="Outflow Categories" groups={outflowGroups} defaultOpen={!!search} />
        <DirectionSection title="Inflow Categories" groups={inflowGroups} defaultOpen={!!search} />
      </div>
    </PageShell>
  )
}
