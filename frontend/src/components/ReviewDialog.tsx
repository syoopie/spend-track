import { Check, ChevronRight, Inbox, ListPlus, Loader2, RotateCcw, Sparkles, Undo2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useCategories, useRuleMatchCount } from '../api/hooks'
import type { AiJobStatus, RuleRerunRowSnapshot } from '../api/types'
import { categoryIcon } from '../lib/categoryColor'
import { fmtDate, fmtSigned } from '../lib/format'
import { CategoryBadge } from './CategoryBadge'
import { Checkbox } from './Checkbox'
import { EmptyState } from './EmptyState'
import { Modal } from './Modal'
import { Select } from './Select'

const AMBER_BG = 'var(--color-warning-surface)'
const AMBER_BADGE_BG = 'var(--color-warning-badge-bg)'
const AMBER_BADGE_FG = 'var(--color-warning-text)'
const AI_BG = 'var(--color-ai-surface)'
const AI_BADGE_BG = 'var(--color-ai-badge-bg)'
const AI_BADGE_FG = 'var(--color-ai-text)'
const SUCCESS_BG = 'var(--color-success-surface)'
const SUCCESS_FG = 'var(--color-success-text)'
// Leading 20px checkbox (REV-1) and 24px chevron (REV-3) columns, ahead of
// the four original Date/Description/Category/Amount columns - shared by
// the column header and every row so they can never drift out of
// alignment with each other.
const ROW_GRID_COLS = 'grid-cols-[20px_24px_80px_1fr_180px_110px]'

// Shared shape both the staging batch's rows and the recategorize batch's
// rows get mapped into, so the row list/popover only need to be written
// once - see StagingReviewDialog.tsx and RecategorizeReviewDialog.tsx.
export interface ReviewRow {
  key: number
  transaction_date: string
  raw_description: string
  matched_label: string | null
  amount: number
  category: string
  subcategory: string | null
  is_excluded: boolean
  exclusion_reason: string | null
  needs_review: boolean
  is_paynow: boolean
  // The rules/contact/PayNow engine's answer before any AI or manual edit -
  // what the single "Restore Default" button falls back to when there's no
  // ai_category to prefer instead.
  original_category: string
  original_label: string | null
  ai_suggested: boolean
  ai_category: string | null
  ai_label: string | null
  ai_rule_pattern: string | null
}

// Whether the row is *currently* showing the AI's proposal - derived by
// comparing against the permanently-recorded ai_category, rather than
// tracked as its own mutable flag, so it can never drift out of sync with
// what's actually applied. Drives the row's AI tint and banner wording.
function aiIsCurrent(row: ReviewRow): boolean {
  return row.ai_category != null && row.category === row.ai_category
}

// Same "would the backend send this row to the AI" test as
// routers/statements.py::_ai_candidates - a row that hasn't been resolved by
// a rule/contact/PayNow match and hasn't come back from the AI yet. Only
// meaningful while aiStatus === 'running': it's what gets pulled into the
// "AI is working on these" group at the top of the row list.
function isAiPending(row: ReviewRow): boolean {
  return !row.ai_suggested && row.matched_label == null && (row.category === 'Others' || row.category === 'Other Income')
}

// The four filter-bar tabs (REV-1 in UI Review.dc.html) - "uncategorized"
// is deliberately not gated on aiStatus the way isAiPending's near-identical
// test is, so it still means something once AI has finished (or was never
// enabled): still sitting in the hidden fallback bucket with no resolution
// of any kind.
type RowFilter = 'all' | 'needs_review' | 'ai_suggested' | 'uncategorized'

function matchesFilter(row: ReviewRow, filter: RowFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'needs_review') return row.needs_review
  if (filter === 'ai_suggested') return row.ai_suggested
  return !row.ai_suggested && !row.needs_review && (row.category === 'Others' || row.category === 'Other Income')
}

function byDateDesc(a: ReviewRow, b: ReviewRow): number {
  return b.transaction_date.localeCompare(a.transaction_date)
}

// The longest run of consecutive letters in `text`, uppercased - a rough
// merchant-keyword extractor. Used to pre-fill Create Rule with something
// that'll actually match a *future* transaction, rather than the entire
// raw bank description (reference numbers, dates and all), which only
// ever matches the one transaction it was copied from (REV-5 in
// UI Review.dc.html).
function tokenizeSuggestion(text: string): string {
  const runs = text.match(/[A-Za-z]+/g) ?? []
  return runs.reduce((longest, r) => (r.length > longest.length ? r : longest), '').toUpperCase()
}

export interface ApplyRowBody {
  category: string
  // Always sent alongside category on a plain edit (never omitted) - the
  // backend applies both together, so leaving this out would silently wipe
  // the label back to null the next time only the category changes.
  matched_label?: string | null
  save_as_contact: boolean
  contact_name?: string
  contact_identifier?: string
  // True only for the single "Restore Default" action - tells the backend
  // to ignore category/matched_label above and instead re-apply
  // ai_category/ai_label if an AI suggestion exists, else
  // original_category/original_label.
  restore_default?: boolean
}

export interface ReviewStatCard {
  label: string
  value: number
  tone?: 'default' | 'muted' | 'amber' | 'ai'
}

function StatCardView({ card }: { card: ReviewStatCard }) {
  if (card.tone === 'amber') {
    return (
      <div className="rounded-2lg px-4.5 py-3" style={{ background: 'var(--color-warning-surface)', border: '1px solid var(--color-warning-surface-border)' }}>
        <div className="text-2xs" style={{ color: 'var(--color-warning-text)' }}>{card.label}</div>
        <div className="text-xl font-bold font-mono" style={{ color: 'var(--color-warning-text)' }}>{card.value}</div>
      </div>
    )
  }
  if (card.tone === 'ai') {
    return (
      <div className="rounded-2lg px-4.5 py-3" style={{ background: AI_BADGE_BG, border: '1px solid var(--color-ai-surface-border)' }}>
        <div className="text-2xs flex items-center gap-1" style={{ color: AI_BADGE_FG }}>
          <Sparkles size={10} className="shrink-0" /> {card.label}
        </div>
        <div className="text-xl font-bold font-mono" style={{ color: AI_BADGE_FG }}>{card.value}</div>
      </div>
    )
  }
  return (
    <div className="bg-input border border-border rounded-2lg px-4.5 py-3">
      <div className="text-2xs text-muted-2">{card.label}</div>
      <div className={`text-xl font-bold font-mono ${card.tone === 'muted' ? 'text-muted-2' : ''}`}>{card.value}</div>
    </div>
  )
}

// One of the popover's independently-saving fields (REV-2 in
// UI Review.dc.html) - restoreDefault counts as its own field rather than
// sharing category/label's slots, since it can be mid-flight at the same
// time a user starts editing category or label by hand.
type FieldKey = 'category' | 'label' | 'contact' | 'restoreDefault'
type FieldStatus = 'idle' | 'pending' | 'saved' | 'error'

// How long a "saved" checkmark stays up before fading back to nothing -
// an error stays until the user acts again (no auto-fade), since it's
// something they need to actually notice.
const SAVED_STATUS_FADE_MS = 1500

function FieldStatusIcon({ status }: { status: FieldStatus }) {
  if (status === 'pending') return <Loader2 size={12} className="animate-spin text-muted-2 shrink-0" />
  if (status === 'saved') return <Check size={12} className="text-success shrink-0" />
  if (status === 'error') return <XCircle size={12} className="shrink-0" style={{ color: 'var(--color-danger-text)' }} />
  return null
}

function ReviewRowPopover({
  row,
  batchRows,
  onApply,
  onCreateRule,
  createRulePending,
}: {
  row: ReviewRow
  // Every row currently in the dialog - used only to compute "matches N
  // transactions in this batch" client-side (REV-5); never mutated here.
  batchRows: ReviewRow[]
  onApply: (body: ApplyRowBody) => Promise<void>
  onCreateRule: (matchPattern: string, targetCategory: string, displayLabel: string | null) => Promise<void>
  createRulePending: boolean
}) {
  const categoriesQ = useCategories()
  const [category, setCategory] = useState(row.category)
  const [label, setLabel] = useState(row.matched_label ?? '')
  // Tracks the last value actually sent to the backend, so a blur that
  // didn't change anything (click into the field, click back out) doesn't
  // fire a redundant request - see applyLabel below.
  const appliedLabelRef = useRef<string | null>(row.matched_label)

  // Re-syncs local state when this row changes from OUTSIDE this popover's
  // own controls while it's open - e.g. the header's "Accept all AI
  // suggestions" bulk action (REV-1) touching this same row. Category is
  // always safe to re-sync immediately (a <select> has no "in-progress
  // typing" to protect). Label only re-syncs when there's no unsaved local
  // edit - if the user is mid-typing something they haven't blurred yet,
  // an external change to this row shouldn't clobber it.
  useEffect(() => {
    setCategory(row.category)
  }, [row.category])
  useEffect(() => {
    if ((label.trim() || null) === appliedLabelRef.current) {
      setLabel(row.matched_label ?? '')
      appliedLabelRef.current = row.matched_label
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.matched_label])
  const [fieldStatus, setFieldStatus] = useState<Record<FieldKey, FieldStatus>>({
    category: 'idle',
    label: 'idle',
    contact: 'idle',
    restoreDefault: 'idle',
  })
  const fadeTimers = useRef<Partial<Record<FieldKey, ReturnType<typeof setTimeout>>>>({})
  // Clears any pending fade timers on unmount - the popover unmounts
  // outright when the row is closed (see the isOpen && <ReviewRowPopover>
  // below), so a fade fired after that would otherwise call setState on an
  // unmounted component.
  useEffect(() => {
    const timers = fadeTimers
    return () => {
      for (const t of Object.values(timers.current)) clearTimeout(t)
    }
  }, [])

  // Applies one field optimistically: shows a spinner immediately (without
  // disabling anything else in the panel - REV-2 in UI Review.dc.html),
  // then a checkmark that fades, or on failure an error icon plus whatever
  // rollback the caller passes (snapping that one field back to its last
  // good value - the query cache itself is rolled back by
  // useUpdateBatchRow's onError in api/hooks.ts, this only reverts this
  // popover's own local input state to match).
  async function applyField(field: FieldKey, body: ApplyRowBody, onFailure?: () => void) {
    const existingTimer = fadeTimers.current[field]
    if (existingTimer) clearTimeout(existingTimer)
    setFieldStatus((s) => ({ ...s, [field]: 'pending' }))
    try {
      await onApply(body)
      setFieldStatus((s) => ({ ...s, [field]: 'saved' }))
      fadeTimers.current[field] = setTimeout(
        () => setFieldStatus((s) => (s[field] === 'saved' ? { ...s, [field]: 'idle' } : s)),
        SAVED_STATUS_FADE_MS,
      )
    } catch {
      setFieldStatus((s) => ({ ...s, [field]: 'error' }))
      onFailure?.()
    }
  }

  // Prefers the AI's own suggested pattern when there is one (still
  // tokenised server-side by the AI prompt to a reusable keyword, not the
  // full description) - otherwise tokenises this row's raw description
  // itself, rather than defaulting to the full string.
  const [rulePattern, setRulePattern] = useState(row.ai_rule_pattern ?? tokenizeSuggestion(row.raw_description))
  const [saveAsContact, setSaveAsContact] = useState(false)

  // Debounced 150ms behind rulePattern, same convention as every other
  // live-filtering input in the app (see docs/ui-conventions.md) - avoids
  // firing a match-count request on every keystroke.
  const [debouncedPattern, setDebouncedPattern] = useState(rulePattern)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedPattern(rulePattern), 150)
    return () => clearTimeout(t)
  }, [rulePattern])

  const trimmedPattern = debouncedPattern.trim()
  // "In this batch" is free - every row already in memory - so it updates
  // instantly even before the debounce settles the backend query below.
  const batchMatchCount = trimmedPattern
    ? batchRows.filter((r) => r.key !== row.key && r.raw_description.toUpperCase().includes(trimmedPattern.toUpperCase())).length
    : 0
  const historyMatchCountQ = useRuleMatchCount(trimmedPattern)
  const historyMatchCount = historyMatchCountQ.data?.count ?? 0
  // +1 for this row itself, which isn't in `batchRows` filtering above and
  // (being uncommitted) can't be in the history count either - so neither
  // half would otherwise count the one transaction the rule is being
  // created *from*.
  const totalMatchCount = 1 + batchMatchCount + historyMatchCount

  const direction = row.amount > 0 ? 'inflow' : 'outflow'
  const categoryOptions = (categoriesQ.data ?? []).filter((c) => c.direction === direction)
  const current = aiIsCurrent(row)
  // What the single "Restore Default" button below resets this row to -
  // the AI's suggestion when one exists, else the rules engine's original
  // answer. Mirrors engine/batch_review.py::apply_row_update's own
  // restore_default branch exactly, so the button's effect can be predicted
  // (and its disabled state computed) without waiting on a round trip.
  const defaultTarget = row.ai_category != null
    ? { category: row.ai_category, label: row.ai_label }
    : { category: row.original_category, label: row.original_label }
  const atDefault = category === defaultTarget.category && (label.trim() || null) === defaultTarget.label

  function applyLabel() {
    const next = label.trim() || null
    if (next === appliedLabelRef.current) return
    const previous = appliedLabelRef.current
    appliedLabelRef.current = next
    applyField('label', { category, matched_label: next, save_as_contact: saveAsContact }, () => {
      appliedLabelRef.current = previous
      setLabel(previous ?? '')
    })
  }

  function restoreDefault() {
    const previousCategory = category
    const previousLabel = appliedLabelRef.current
    setCategory(defaultTarget.category)
    setLabel(defaultTarget.label ?? '')
    appliedLabelRef.current = defaultTarget.label
    applyField('restoreDefault', { category, save_as_contact: false, restore_default: true }, () => {
      setCategory(previousCategory)
      setLabel(previousLabel ?? '')
      appliedLabelRef.current = previousLabel
    })
  }

  return (
    <div
      className="px-5 py-4 flex flex-col gap-3 border-b border-border"
      style={{ background: row.ai_suggested && current ? AI_BG : row.needs_review ? AMBER_BG : 'var(--color-input)' }}
    >
      {/* Restore Default lives here, not squeezed into the category row below
          - that row's other occupant (the PayNow "save as contact" checkbox)
          only exists on some rows, which used to shift the button sideways
          depending on row type. Anchoring it to this always-present header
          row keeps it in the same spot for every row, and pairs it visually
          with the AI copy it's the direct undo/redo for. */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {row.ai_suggested && current && (
            <div className="text-2xs flex items-center gap-1.5" style={{ color: AI_BADGE_FG }}>
              <Sparkles size={11} className="shrink-0" />
              AI suggested this category and label — edit them below if you'd like.
            </div>
          )}
          {row.ai_suggested && !current && (
            <div className="text-2xs flex items-center gap-1.5" style={{ color: 'var(--color-muted-2)' }}>
              <Sparkles size={11} className="shrink-0" />
              AI suggested "{row.ai_category}" for this transaction — you're not using that suggestion right now.
            </div>
          )}
        </div>
        {/* Single button regardless of AI/manual-edit state - it always
            resets to the same predictable target (see defaultTarget above),
            so there's no separate "reject" vs "restore" decision for the
            user to make; disabled once the row already matches that target.
            No longer gated on a panel-wide applyPending (REV-2) - just its
            own field's status, so editing category/label elsewhere in this
            same popover can't block it or vice versa. */}
        <button
          onClick={restoreDefault}
          disabled={fieldStatus.restoreDefault === 'pending' || atDefault}
          title={
            row.ai_category != null
              ? "Reset to the AI's suggested category and display name"
              : 'Reset to the original category and display name'
          }
          className="shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-border bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <FieldStatusIcon status={fieldStatus.restoreDefault} />
          <RotateCcw size={12} className="shrink-0" />
          Restore Default
        </button>
      </div>
      <div>
        <div className="text-2xs text-muted mb-1 flex items-center gap-1.5">
          Display name
          <FieldStatusIcon status={fieldStatus.label} />
        </div>
        {/* Applies on blur/Enter, not per keystroke - unlike category/the
            checkbox, which fire on their own discrete change events. Never
            disabled while pending (REV-2) - the field's own status icon
            above is the only feedback that a save is in flight. */}
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={applyLabel}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }}
          placeholder={row.raw_description}
          className="w-full box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-md"
        />
      </div>
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="text-2xs text-muted mb-1 flex items-center gap-1.5">
            Assign category · {direction === 'inflow' ? 'Inflow' : 'Outflow'}
            <FieldStatusIcon status={fieldStatus.category} />
          </div>
          {/* Picking a category applies it immediately - no separate Apply
              button. Re-picking the row's current value is a no-op (nothing
              actually changed), so it doesn't fire a redundant request. */}
          <Select
            uiSize="sm"
            value={category}
            onChange={(e) => {
              const next = e.target.value
              const previous = category
              setCategory(next)
              if (next !== previous) {
                applyField('category', { category: next, matched_label: label.trim() || null, save_as_contact: saveAsContact }, () =>
                  setCategory(previous),
                )
              }
            }}
            className="w-full"
          >
            {categoryOptions.map((c) => {
              const Icon = categoryIcon(categoriesQ.data, c.name)
              return (
                <option key={c.id} value={c.name}>
                  <span className="inline-flex items-center gap-1.5">
                    <Icon size={12} className="shrink-0" />
                    {c.name}
                  </span>
                </option>
              )
            })}
          </Select>
        </div>
        {/* A PayNow line's "match text" is a free-text payee name, not a
            reusable merchant keyword, so it's never rule-eligible - the only
            way to resolve it going forward is a contact mapping. Every other
            row is the reverse: no identifiable payee to attach a contact
            to, so it gets the "Create a rule" section below instead.
            Toggling this also applies immediately (paired with whatever
            category/label are currently set), so it works whichever order
            the controls are used in. */}
        {row.is_paynow && (
          <label className="flex items-center gap-1.5 text-xs text-text pb-2 cursor-pointer">
            <Checkbox
              checked={saveAsContact}
              onChange={(next) => {
                const previous = saveAsContact
                setSaveAsContact(next)
                applyField('contact', { category, matched_label: label.trim() || null, save_as_contact: next }, () =>
                  setSaveAsContact(previous),
                )
              }}
            />
            Save as contact mapping
            <FieldStatusIcon status={fieldStatus.contact} />
          </label>
        )}
      </div>
      {/* Deliberately its own row with its own button, not a checkbox bolted
          onto Apply above - applying a category to this one transaction and
          creating a rule that resolves every matching transaction going
          forward (including elsewhere in this same batch, via the rerun
          this triggers server-side) are two different actions with two
          different blast radii, so they get two different confirmations. */}
      {!row.is_paynow && (
        <div className="flex items-end gap-3 pt-3 border-t border-border/70">
          <div className="flex-1">
            <div className="text-2xs text-muted mb-1">
              Create a rule — future transactions containing this text will be categorized as{' '}
              <span className="text-text font-medium">{category}</span>
              {label.trim() && (
                <>
                  , labeled <span className="text-text font-medium">{label.trim()}</span>
                </>
              )}{' '}
              automatically
            </div>
            <input
              value={rulePattern}
              onChange={(e) => setRulePattern(e.target.value)}
              placeholder={row.raw_description}
              className="w-full box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-xs font-mono"
            />
            {/* Live match count (REV-5) - lets a user see, before creating
                the rule, whether the pattern they typed is a reusable
                merchant keyword or something so specific it'll only ever
                match this one transaction. The batch half is instant
                (already in memory); the history half trails the debounce
                by one round trip. */}
            {trimmedPattern && (
              <div className="text-2xs text-muted-2 mt-1">
                Matches {batchMatchCount} other transaction{batchMatchCount === 1 ? '' : 's'} in this batch
                {historyMatchCountQ.isFetching ? (
                  ', checking history…'
                ) : (
                  <>, {historyMatchCount} in history</>
                )}
              </div>
            )}
          </div>
          <button
            onClick={() => onCreateRule(rulePattern.trim(), category, label.trim() || null)}
            disabled={createRulePending || !rulePattern.trim() || totalMatchCount <= 1}
            title={
              rulePattern.trim() && totalMatchCount <= 1
                ? "This pattern doesn't match anything else - it would only ever apply to this one transaction"
                : undefined
            }
            className="shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-lg border border-border bg-transparent text-text hover:bg-input cursor-pointer disabled:opacity-60 whitespace-nowrap"
          >
            <ListPlus size={13} className="shrink-0" />
            Create Rule
          </button>
        </div>
      )}
    </div>
  )
}

export function ReviewDialog({
  title,
  subtitle,
  onClose,
  statCards,
  aiStatus,
  aiWarning,
  aiModel,
  rows,
  onApplyRow,
  onCreateRule,
  createRulePending,
  onUndoRule,
  undoRulePending,
  footer,
  emptyMessage = 'Nothing to show.',
}: {
  title: string
  subtitle: string
  onClose: () => void
  statCards: ReviewStatCard[]
  aiStatus: AiJobStatus
  aiWarning: string | null
  aiModel: string | null
  rows: ReviewRow[]
  onApplyRow: (row: ReviewRow, body: ApplyRowBody) => Promise<void>
  onCreateRule: (
    row: ReviewRow,
    matchPattern: string,
    targetCategory: string,
    displayLabel: string | null,
  ) => Promise<{ rule_id: number; updated_rows: RuleRerunRowSnapshot[] }>
  createRulePending: boolean
  onUndoRule: (payload: { rule_id: number; rows: RuleRerunRowSnapshot[] }) => Promise<void>
  undoRulePending: boolean
  footer: ReactNode
  emptyMessage?: string
}) {
  const [openKey, setOpenKey] = useState<number | null>(null)
  const [ruleBanner, setRuleBanner] = useState<{
    ruleId: number
    rows: RuleRerunRowSnapshot[]
    matchPattern: string
    category: string
  } | null>(null)
  const categoriesQ = useCategories()
  // Row header refs, keyed by row.key - lets keyboard Up/Down move focus
  // between rows (REV-3) and lets opening a row scroll it to the top of the
  // scroller below, rather than the newly-opened popover shoving everything
  // below it down inside a fixed-height scroll region.
  const rowRefs = useRef(new Map<number, HTMLDivElement>())
  const scrollerRef = useRef<HTMLDivElement>(null)
  const columnHeaderRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (openKey == null) return
    const rowEl = rowRefs.current.get(openKey)
    const scroller = scrollerRef.current
    if (!rowEl || !scroller) return
    const headerHeight = columnHeaderRef.current?.offsetHeight ?? 0
    scroller.scrollTop = rowEl.offsetTop - scroller.offsetTop - headerHeight
  }, [openKey])

  // REV-1: a filter bar + search over the row list, so reviewing a
  // 100+-row batch doesn't mean scrolling past everything already resolved
  // to find what still needs attention.
  const [rowFilter, setRowFilter] = useState<RowFilter>('all')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 150)
    return () => clearTimeout(t)
  }, [search])

  const filterCounts = {
    all: rows.length,
    needs_review: rows.filter((r) => matchesFilter(r, 'needs_review')).length,
    ai_suggested: rows.filter((r) => matchesFilter(r, 'ai_suggested')).length,
    uncategorized: rows.filter((r) => matchesFilter(r, 'uncategorized')).length,
  }
  const stillNeedsReviewCount = filterCounts.needs_review + filterCounts.uncategorized

  const q = debouncedSearch.trim().toLowerCase()
  const visibleRows = rows.filter((r) => {
    if (!matchesFilter(r, rowFilter)) return false
    if (!q) return true
    return (
      (r.matched_label ?? '').toLowerCase().includes(q) ||
      r.raw_description.toLowerCase().includes(q) ||
      r.category.toLowerCase().includes(q)
    )
  })

  // Multi-select with shift-click ranges (REV-1) - bulkApply below is what
  // both the bulk action bar and "Accept all AI suggestions" run against.
  const [selectedKeys, setSelectedKeys] = useState<Set<number>>(new Set())
  const lastClickedIndexRef = useRef<number | null>(null)
  const [bulkPending, setBulkPending] = useState(false)

  // Clears the selection whenever the visible set changes shape (a new
  // filter/search) - a selection made against one filtered view silently
  // carrying over into a different one would be surprising and hard to
  // reason about ("14 selected" for rows you can no longer even see).
  useEffect(() => {
    setSelectedKeys(new Set())
  }, [rowFilter, debouncedSearch])

  function toggleSelect(key: number, index: number, shiftKey: boolean) {
    // Captured BEFORE the ref is overwritten below, and passed into the
    // updater as a value rather than read live from the ref inside it -
    // setSelectedKeys's updater runs asynchronously (deferred to React's
    // next render pass), so by the time it actually executes,
    // lastClickedIndexRef.current has already been reassigned to `index`
    // by the synchronous line at the end of this function. Reading the
    // ref live from inside the updater made from/to collapse to the same
    // value every time, silently turning every shift-click into a
    // single-row toggle instead of a range.
    const anchorIndex = lastClickedIndexRef.current
    setSelectedKeys((prev) => {
      const next = new Set(prev)
      if (shiftKey && anchorIndex != null) {
        const [from, to] = [anchorIndex, index].sort((a, b) => a - b)
        for (let i = from; i <= to; i++) {
          const k = orderedRows[i]?.key
          if (k != null) next.add(k)
        }
      } else if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
    lastClickedIndexRef.current = index
  }

  async function bulkApply(targetRows: ReviewRow[], body: (row: ReviewRow) => ApplyRowBody) {
    setBulkPending(true)
    try {
      await Promise.allSettled(targetRows.map((r) => onApplyRow(r, body(r))))
    } finally {
      setBulkPending(false)
      setSelectedKeys(new Set())
    }
  }

  function acceptAiSuggestion(row: ReviewRow): ApplyRowBody {
    return { category: row.ai_category ?? row.category, matched_label: row.ai_label, save_as_contact: false }
  }

  // Every AI suggestion not already applied - across the whole batch,
  // regardless of the current filter/search/selection - what "Accept all"
  // beside the status pill operates on.
  const acceptableAiRows = rows.filter((r) => r.ai_suggested && !aiIsCurrent(r))

  // While AI categorization is running, its not-yet-resolved candidates get
  // pulled into their own group at the very top of the row list (highest
  // priority, above even already-resolved ai_suggested/needs_review rows),
  // sorted by date within the group - see isAiPending. The running banner
  // moves from a generic top-of-dialog notice to sitting right on this
  // group, so the "still working" state and the rows it's working on read
  // as one unit. If no rows currently qualify (e.g. they're all filtered
  // out as duplicates), fall back to the old top-of-dialog banner instead
  // of showing an empty group header.
  const aiPendingRows = aiStatus === 'running' ? visibleRows.filter(isAiPending).sort(byDateDesc) : []
  const aiPendingKeys = new Set(aiPendingRows.map((r) => r.key))
  const otherRows = [...visibleRows]
    .filter((r) => !aiPendingKeys.has(r.key))
    .sort((a, b) => Number(b.ai_suggested) - Number(a.ai_suggested) || byDateDesc(a, b))
  // The actual on-screen row order, computed once - both the render below
  // and the ArrowUp/ArrowDown keyboard handler (REV-3) walk this same
  // array, so "next row" always means the same thing to both.
  const orderedRows = [...aiPendingRows, ...otherRows]

  return (
    <Modal onClose={onClose} width={860}>
      <div className="flex items-start justify-between mb-0.5">
        <div>
          <div className="text-lg font-bold">{title}</div>
          <div className="text-md text-muted mt-0.5 mb-4 flex items-center gap-2 flex-wrap">
            <span>{subtitle}</span>
            {/* A persistent, always-visible status pill - unlike the group
                header/footer text below (which only appear while scrolled to
                the right spot, or only for specific states), this reflects
                every non-disabled aiStatus at a glance, including "done" -
                which otherwise had no banner of its own anywhere in this
                dialog once the running group disappeared. */}
            {aiStatus !== 'disabled' && (
              <span
                className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded-full shrink-0"
                style={
                  aiStatus === 'failed'
                    ? { background: 'var(--color-danger-badge-bg)', color: 'var(--color-danger-badge-fg)' }
                    : aiStatus === 'done'
                      ? { background: SUCCESS_BG, color: SUCCESS_FG }
                      : { background: AI_BADGE_BG, color: AI_BADGE_FG }
                }
              >
                {aiStatus === 'running' && <Loader2 size={10} className="animate-spin shrink-0" />}
                {aiStatus === 'running' && 'AI categorizing…'}
                {aiStatus === 'done' && 'AI categorization complete'}
                {aiStatus === 'failed' && 'AI categorization failed'}
              </span>
            )}
            {/* Bulk-accepts every not-yet-applied AI suggestion in one
                click (REV-1) - the same per-row apply as picking a
                suggestion by hand, just looped, so a 30-row AI pass
                doesn't mean opening 30 popovers one at a time. */}
            {acceptableAiRows.length > 0 && (
              <button
                onClick={() => bulkApply(acceptableAiRows, acceptAiSuggestion)}
                disabled={bulkPending}
                className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded-full border border-border bg-transparent text-text hover:bg-input cursor-pointer disabled:opacity-60 shrink-0"
              >
                <Sparkles size={10} className="shrink-0" />
                Accept all {acceptableAiRows.length} AI suggestion{acceptableAiRows.length === 1 ? '' : 's'}
              </button>
            )}
          </div>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-text text-lg leading-none cursor-pointer border-none bg-transparent"
        >
          ×
        </button>
      </div>

      {/* Purely informational - never disables the × above, so the dialog is
          always dismissible while this runs. Individual callers may disable
          their own footer actions during this state (e.g. staging disables
          Commit) - see each dialog's own footer. The background AI job keeps
          running whether this dialog is open or closed; closing just stops
          watching it. */}
      {aiStatus === 'running' && aiPendingRows.length === 0 && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 flex items-center gap-2 text-xs"
          style={{ background: AI_BG, color: AI_BADGE_FG }}
        >
          <Loader2 size={14} className="animate-spin shrink-0" />
          AI is categorizing leftover transactions with {aiModel}… you can keep working, or close this and check
          back later.
        </div>
      )}
      {aiStatus === 'failed' && aiWarning && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 text-xs"
          style={{ background: 'var(--color-warning-surface)', color: 'var(--color-warning-text)' }}
        >
          {aiWarning}
        </div>
      )}

      {/* Confirms the "Create Rule" action and offers to back it out - a
          rule can retroactively recategorize other rows elsewhere in this
          same batch, so it gets its own persistent (non-fading) banner
          rather than the plain "popover just closes" feedback a regular
          Apply gets. Stays up until dismissed, undone, or replaced by a
          newer rule creation. */}
      {ruleBanner && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 flex items-center justify-between gap-3 text-xs"
          style={{ background: SUCCESS_BG, color: SUCCESS_FG }}
        >
          <div>
            Rule created — "{ruleBanner.matchPattern}" now categorizes as{' '}
            <span className="font-semibold">{ruleBanner.category}</span>. Applied to {ruleBanner.rows.length}{' '}
            transaction{ruleBanner.rows.length === 1 ? '' : 's'} in this batch.
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={async () => {
                try {
                  await onUndoRule({ rule_id: ruleBanner.ruleId, rows: ruleBanner.rows })
                  setRuleBanner(null)
                } catch {
                  // leave the banner up so the user can retry the undo
                }
              }}
              disabled={undoRulePending}
              className="text-2xs font-semibold px-2.5 py-1.5 rounded-md bg-transparent cursor-pointer inline-flex items-center gap-1 disabled:opacity-60"
              style={{ color: SUCCESS_FG, border: '1px solid currentColor' }}
            >
              <Undo2 size={11} /> Undo
            </button>
            <button
              onClick={() => setRuleBanner(null)}
              className="text-base leading-none cursor-pointer border-none bg-transparent"
              style={{ color: SUCCESS_FG }}
            >
              ×
            </button>
          </div>
        </div>
      )}

      {statCards.length > 0 && (
        <div className="flex gap-3 mb-3 flex-wrap">
          {statCards.map((c) => (
            <StatCardView key={c.label} card={c} />
          ))}
        </div>
      )}

      {/* What each row tint means - four tinted states with no legend used
          to be its own finding (REV-6 in UI Review.dc.html): amber, violet,
          and a barely-distinguishable 75%-opacity violet variant, with a
          sparkle icon that meant two different things depending on color. */}
      {rows.length > 0 && (
        <div className="flex items-center gap-4 mb-3 text-2xs text-muted-2 flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: 'var(--color-warning-text)' }} />
            Needs review
          </span>
          <span className="flex items-center gap-1.5">
            <Sparkles size={10} className="shrink-0" style={{ color: AI_BADGE_FG }} />
            AI suggested
          </span>
          <span className="flex items-center gap-1.5">
            <Loader2 size={10} className="shrink-0" style={{ color: AI_BADGE_FG }} />
            AI still working
          </span>
        </div>
      )}

      {/* Filter bar + search (REV-1) - without this, resolving a 100+-row
          batch means scrolling past everything already fine to find what
          still needs attention, with no way to see just the unresolved
          ones. */}
      {rows.length > 0 && (
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          {(
            [
              ['all', `All (${filterCounts.all})`],
              ['needs_review', `Needs review (${filterCounts.needs_review})`],
              ['ai_suggested', `AI suggested (${filterCounts.ai_suggested})`],
              ['uncategorized', `Uncategorized (${filterCounts.uncategorized})`],
            ] as [RowFilter, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setRowFilter(key)}
              disabled={key !== 'all' && filterCounts[key] === 0}
              className={`text-2xs font-semibold px-2.5 py-1 rounded-full border cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                rowFilter === key ? 'border-accent bg-accent/15 text-accent' : 'border-border bg-transparent text-muted hover:text-text'
              }`}
            >
              {label}
            </button>
          ))}
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search…"
            className="ml-auto w-[160px] box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-xs"
          />
        </div>
      )}

      {/* Appears only once something's selected - "N selected — set
          category, accept AI suggestion" (REV-1). */}
      {selectedKeys.size > 0 && (
        <div className="flex items-center gap-2.5 mb-3 px-3.5 py-2 rounded-lg border border-accent/40 bg-accent/10 flex-wrap">
          <span className="text-xs font-semibold text-text">{selectedKeys.size} selected</span>
          <Select
            uiSize="sm"
            value=""
            disabled={bulkPending}
            onChange={(e) => {
              const targetCategory = e.target.value
              if (!targetCategory) return
              bulkApply(orderedRows.filter((r) => selectedKeys.has(r.key)), (r) => ({
                category: targetCategory,
                matched_label: r.matched_label,
                save_as_contact: false,
              }))
            }}
            className="w-[190px]"
          >
            <option value="">Set category to…</option>
            {(categoriesQ.data ?? []).map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </Select>
          {orderedRows.some((r) => selectedKeys.has(r.key) && r.ai_suggested && !aiIsCurrent(r)) && (
            <button
              onClick={() =>
                bulkApply(
                  orderedRows.filter((r) => selectedKeys.has(r.key) && r.ai_suggested && !aiIsCurrent(r)),
                  acceptAiSuggestion,
                )
              }
              disabled={bulkPending}
              className="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-border bg-transparent text-text hover:bg-input cursor-pointer disabled:opacity-60"
            >
              <Sparkles size={12} className="shrink-0" />
              Accept AI suggestion
            </button>
          )}
          <button
            onClick={() => setSelectedKeys(new Set())}
            className="ml-auto text-2xs text-muted hover:text-text bg-transparent border-none cursor-pointer"
          >
            Clear selection
          </button>
        </div>
      )}

      <div ref={scrollerRef} className="bg-input border border-border rounded-xl overflow-y-auto mb-5 max-h-[45vh]">
        <div
          ref={columnHeaderRef}
          className={`grid ${ROW_GRID_COLS} px-5 py-2.5 text-2xs text-muted-2 uppercase tracking-wide border-b border-border/70 sticky top-0 bg-input`}
        >
          <div />
          <div />
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div className="text-right">Amount</div>
        </div>
        {rows.length === 0 && <EmptyState icon={Inbox} title={emptyMessage} />}
        {rows.length > 0 && visibleRows.length === 0 && (
          <EmptyState icon={Inbox} title="No rows match this filter" />
        )}
        {/* Every row is reviewable/clickable regardless of AI or needs_review
            state - adding a rule or contact mapping shouldn't be gated on
            whether AI touched the row. Base ordering is most-recent-first;
            layered on top, already-resolved ai_suggested rows are stably
            sorted to the top of the "rest" group so they're easy to find,
            and - while AI is still running - its not-yet-resolved
            candidates get pulled into their own group above everything
            else, with the "still working" banner riding along as that
            group's header instead of a separate dialog-wide notice. */}
        {aiPendingRows.length > 0 && (
          <div
            className="px-5 py-2 flex items-center gap-2 text-2xs border-b border-border/70"
            style={{ background: AI_BG, color: AI_BADGE_FG }}
          >
            <Loader2 size={12} className="animate-spin shrink-0" />
            AI is categorizing these {aiPendingRows.length} transaction{aiPendingRows.length === 1 ? '' : 's'} with{' '}
            {aiModel}… you can keep working, or close this and check back later.
          </div>
        )}
        {orderedRows.map((row, i) => {
          const isOpen = openKey === row.key
          const current = aiIsCurrent(row)
          const pending = aiPendingKeys.has(row.key)
          const colorOverride = row.needs_review
            ? { bg: AMBER_BADGE_BG, fg: AMBER_BADGE_FG }
            : row.ai_suggested && current
              ? { bg: AI_BADGE_BG, fg: AI_BADGE_FG }
              : undefined
          const rowBg = pending
            ? AI_BG
            : row.needs_review
              ? AMBER_BG
              : row.ai_suggested && current
                ? AI_BG
                : undefined
          return (
            <div key={row.key}>
              <div
                ref={(el) => {
                  if (el) rowRefs.current.set(row.key, el)
                  else rowRefs.current.delete(row.key)
                }}
                role="button"
                tabIndex={0}
                aria-expanded={isOpen}
                onClick={() => setOpenKey(isOpen ? null : row.key)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    setOpenKey(isOpen ? null : row.key)
                  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                    e.preventDefault()
                    const next = orderedRows[i + (e.key === 'ArrowDown' ? 1 : -1)]
                    if (next) rowRefs.current.get(next.key)?.focus()
                  }
                }}
                className={`grid ${ROW_GRID_COLS} items-center px-5 py-2.5 text-md border-b border-border/70 cursor-pointer
                  hover:ring-1 hover:ring-inset hover:ring-accent/40 focus-visible:outline focus-visible:outline-2
                  focus-visible:-outline-offset-2 focus-visible:outline-accent`}
                style={{ background: rowBg ?? (isOpen ? 'var(--color-input)' : undefined) }}
              >
                {/* preventDefault stops the checkbox's own native toggle so
                    toggleSelect (which supports shift-click ranges) is the
                    only thing driving its checked state; stopPropagation
                    keeps this click from also opening the row below. */}
                <div
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    toggleSelect(row.key, i, e.shiftKey)
                  }}
                >
                  <Checkbox checked={selectedKeys.has(row.key)} onChange={() => {}} />
                </div>
                <ChevronRight size={14} className={`shrink-0 text-muted-2 transition-transform ${isOpen ? 'rotate-90' : ''}`} />
                <div className="text-muted font-mono text-xs">{fmtDate(row.transaction_date)}</div>
                <div className="min-w-0 pr-2 flex items-center gap-1.5">
                  {(row.ai_suggested || pending) && (
                    <Sparkles
                      size={11}
                      className={`shrink-0 ${pending ? 'animate-pulse' : ''}`}
                      style={{ color: current || pending ? AI_BADGE_FG : 'var(--color-muted-2)' }}
                    />
                  )}
                  <div className="min-w-0">
                    <div className="truncate">{row.matched_label ?? row.raw_description}</div>
                    {/* The clean label/AI suggestion is never the only thing shown - the
                        full raw bank description stays visible underneath it, not just
                        in a hover title, so it's never hidden behind an edited name. */}
                    {row.matched_label && (
                      <div className="truncate text-2xs text-muted-2" title={row.raw_description}>
                        {row.raw_description}
                      </div>
                    )}
                  </div>
                </div>
                <div>
                  {/* A shimmer placeholder, not a dimmed row - opacity-0.75
                      on the whole row used to read as "this row is
                      disabled", when the category is really the only thing
                      not settled yet while AI works (REV-6). */}
                  {pending ? (
                    <div className="h-5 w-24 rounded-full bg-border animate-pulse" />
                  ) : (
                    <CategoryBadge category={row.category} categories={categoriesQ.data} colorOverride={colorOverride} />
                  )}
                </div>
                <div className={`text-right font-mono ${row.amount > 0 ? 'text-success' : 'text-text'}`}>
                  {fmtSigned(row.amount)}
                </div>
              </div>
              {isOpen && (
                <ReviewRowPopover
                  row={row}
                  batchRows={rows}
                  onApply={async (body) => {
                    // Deliberately doesn't close the popover on success (even
                    // on failure, there's nothing to undo here) - the whole
                    // point of auto-apply-on-change (category, label,
                    // save-as-contact, restore default) is that each control
                    // can be used independently without losing the others;
                    // forcing a close after the first one would cut that
                    // short. The row header's own click toggle is still how
                    // the user closes it when done.
                    try {
                      await onApplyRow(row, body)
                    } catch {
                      // swallow - nothing else to do here; the user can just retry
                    }
                  }}
                  createRulePending={createRulePending}
                  onCreateRule={async (matchPattern, targetCategory, displayLabel) => {
                    try {
                      const result = await onCreateRule(row, matchPattern, targetCategory, displayLabel)
                      setOpenKey(null)
                      setRuleBanner({
                        ruleId: result.rule_id,
                        rows: result.updated_rows,
                        matchPattern,
                        category: targetCategory,
                      })
                    } catch {
                      // leave the popover open on failure so the user can retry
                    }
                  }}
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-end gap-3">
        {/* "12 of 104 still need review" (REV-1) - each caller's own footer
            (Commit/Discard) is composed alongside it, not inside it, so
            this stays true regardless of which dialog is showing it. */}
        {stillNeedsReviewCount > 0 && (
          <div className="text-2xs text-muted mr-auto">
            {stillNeedsReviewCount} of {rows.length} still need{stillNeedsReviewCount === 1 ? 's' : ''} review
          </div>
        )}
        {footer}
      </div>
    </Modal>
  )
}
