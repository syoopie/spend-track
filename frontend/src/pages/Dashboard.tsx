import { ArrowDown, ArrowUp, FileUp, LayoutGrid, Loader2, Pencil, Receipt, RefreshCw, SearchX, SlidersHorizontal, Trash2 } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useAccounts,
  useCategories,
  useCurrentRecategorizeBatch,
  useDashboardSummary,
  useDeleteTransaction,
  useMonthlyTotals,
  useSettings,
  useTransactions,
} from '../api/hooks'
import { ElapsedTimer } from '../components/ElapsedTimer'
import { useToast } from '../components/Toast'
import { fmtDate, fmtMonthRangeLabel, fmtMonthYearLabel, fmtPlain, fmtSigned, shiftMonth } from '../lib/format'
import { loadDashboardFilters, saveDashboardFilters, type DashboardFilters, type DirectionFilter } from '../lib/dashboardFilters'
import { CashFlowChart, cashFlowQualifier } from '../components/CashFlowChart'
import { CategoryBadge, CategoryLabel } from '../components/CategoryBadge'
import { categoryOptionElements } from '../components/CategoryOptions'
import { CategoryDonut } from '../components/CategoryDonut'
import { VelocityChart } from '../components/VelocityChart'
import { RefundDrawer } from '../components/RefundDrawer'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { DataTableHeader, dataTableGridTemplate, type DataTableColumn } from '../components/DataTable'
import { DateRangePicker } from '../components/DateRangePicker'
import { EmptyState, ErrorState } from '../components/EmptyState'
import { Input } from '../components/Field'
import { TransactionEditPopover } from '../components/TransactionEditPopover'
import { RecategorizeReviewDialog } from '../components/RecategorizeReviewDialog'
import { Checkbox } from '../components/Checkbox'
import { Select } from '../components/Select'
import { Tabs } from '../components/Tabs'
import { useUploadDialog } from '../components/UploadProvider'
import type { Transaction, TopEntry } from '../api/types'

const PAGE_SIZE = 100

type SortField = 'date' | 'amount'
type SortDir = 'asc' | 'desc'

// DASH-2 in UI Review.dc.html: "Top Category" used to render a category
// name through the same 24px mono numeric slot as the other three cards -
// it read like a broken number and would overflow on a long category name.
// `variant="text"` gives non-numeric values their own smaller, wrapping
// sans-serif treatment instead. Deliberately NOT switched to font-display:
// FEED-4 pinned font-mono + tabular-nums specifically so digit columns
// align across cards/charts, and Space Grotesk doesn't carry that guarantee
// - X-8's "extend font-display to metric values" is applied to labels and
// titles instead, not the numeric value itself, to avoid undoing FEED-4.
function MetricCard({
  label,
  value,
  valueClassName = '',
  hint,
  variant = 'number',
  delta,
}: {
  label: string
  value: string
  valueClassName?: string
  hint?: string
  variant?: 'number' | 'text'
  delta?: ReactNode
}) {
  return (
    <Card padding="p-4.5">
      <div className="text-xs text-muted mb-2">{label}</div>
      <div
        className={
          variant === 'text'
            ? `text-md font-semibold leading-snug line-clamp-2 ${valueClassName}`
            : `text-2xl font-bold font-mono ${valueClassName}`
        }
      >
        {value}
      </div>
      {delta}
      {hint && <div className="text-xs text-muted-2 mt-1">{hint}</div>}
    </Card>
  )
}

// The same same-day-of-period comparison VelocityChart already computes
// (spend_velocity's last point) reused for a metric-card delta (DASH-2) -
// no second backend computation needed. Outflow only, since that's the one
// figure the backend tracks a previous-period cumulative for; a rise in
// outflow is coloured as the "worse" direction (danger), a fall as
// "better" (success) - the opposite of how a rising number reads
// everywhere else in the app, but correct for spending.
function OutflowDelta({ current, previous, prevLabel }: { current: number; previous: number; prevLabel: string }) {
  if (previous <= 0) return null
  const pct = Math.round(((current - previous) / previous) * 100)
  if (pct === 0) return <div className="text-xs text-muted-2 mt-1">Flat vs {prevLabel}</div>
  const up = pct > 0
  const Icon = up ? ArrowUp : ArrowDown
  return (
    <div className={`flex items-center gap-1 text-xs mt-1 ${up ? 'text-danger-text' : 'text-success'}`}>
      <Icon size={11} />
      {up ? '+' : ''}
      {pct}% vs {prevLabel}
    </div>
  )
}

// Merchants/PayNow used to render as plain text rows with no visual sense of
// scale - a $6 tap and a $600 tap looked identical apart from the digits
// (DASH-4 in UI Review.dc.html). A proportional bar behind the row gives
// the same at-a-glance read the donut's ring already provides for
// categories.
function RankedBarRow({ entry, maxAmount }: { entry: TopEntry; maxAmount: number }) {
  const pct = maxAmount > 0 ? (entry.amount / maxAmount) * 100 : 0
  return (
    <div className="relative py-1">
      <div className="absolute inset-y-1 left-0 rounded bg-accent/12" style={{ width: `${pct}%` }} />
      <div className="relative flex justify-between text-md px-1.5">
        <span className="truncate pr-2">{entry.name}</span>
        <span className="font-mono text-text-2 shrink-0">{fmtPlain(entry.amount)}</span>
      </div>
    </div>
  )
}

// Column definitions for the feed's header row (X-6 in UI Review.dc.html) -
// DataTableHeader drives the sortable date/category/amount columns from
// this one array instead of a hand-rolled SortableHeader repeated per
// column. The BODY rows below intentionally do NOT go through DataTable's
// row/cell wrapper: each row is its own role="button" (click opens the
// transaction editor, arrow keys move between rows) - a legitimate, already
// -accessible pattern, just not the ARIA grid-row one. Forcing
// role="gridcell" onto cells inside a role="button" row would misdescribe
// what they are, not fix a real gap - see DataTable.tsx's own comment.
const FEED_COLUMNS: DataTableColumn<SortField>[] = [
  { key: 'date', header: 'Date', width: '76px', sortKey: 'date' },
  { key: 'description', header: 'Description', width: 'minmax(0,1fr)' },
  { key: 'category', header: 'Category', width: '168px' },
  { key: 'account', header: 'Account', width: '120px' },
  { key: 'amount', header: 'Amount', width: '120px', align: 'right', sortKey: 'amount' },
  { key: 'refund', header: '', width: '28px' },
  { key: 'edit', header: '', width: '52px' },
]
const FEED_GRID_TEMPLATE = dataTableGridTemplate(FEED_COLUMNS)

// Wraps the first case-insensitive occurrence of `query` in `text` with a
// highlight span - only ever called with the debounced query, and silently
// no-ops (returns the plain text) when the query doesn't appear in this
// particular field, e.g. it matched via raw_description while the label is
// what's actually being displayed.
function highlightMatch(text: string, query: string): ReactNode {
  if (!query.trim()) return text
  const idx = text.toLowerCase().indexOf(query.trim().toLowerCase())
  if (idx === -1) return text
  const end = idx + query.trim().length
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-accent/30 text-inherit rounded-[2px]">{text.slice(idx, end)}</mark>
      {text.slice(end)}
    </>
  )
}

/** "a UOB" / "a UOB or DBS" / "a UOB, DBS, or OCBC" - built from the API's
 * own list of banks that actually parse, so the first-run copy can't keep
 * naming a bank whose parser doesn't exist yet (or drop one that just
 * landed). */
function bankListLabel(banks: string[]): string {
  if (banks.length === 0) return 'a bank'
  if (banks.length === 1) return `a ${banks[0]}`
  if (banks.length === 2) return `a ${banks[0]} or ${banks[1]}`
  return `a ${banks.slice(0, -1).join(', ')}, or ${banks[banks.length - 1]}`
}

// Undo window for a feed row's delete action - mirrors Rules.tsx's
// DELETE_UNDO_MS (row hidden immediately, real DELETE deferred so a
// misclick is recoverable). Kept as its own copy rather than a shared
// constant since the two screens have no other coupling.
const DELETE_UNDO_MS = 6000

// A three-way All/In/Out segmented control, not a third <Select> - it's the
// filter the user reaches for most often alongside search/category, so it
// stays a single click rather than a dropdown open+pick.
function DirectionToggle({
  value,
  onChange,
}: {
  value: DirectionFilter | undefined
  onChange: (next: DirectionFilter | undefined) => void
}) {
  const options: { key: DirectionFilter | undefined; label: string }[] = [
    { key: undefined, label: 'All' },
    { key: 'inflow', label: 'In' },
    { key: 'outflow', label: 'Out' },
  ]
  return (
    <div className="flex items-center rounded-lg border border-border bg-input p-0.5 text-xs shrink-0">
      {options.map((o) => (
        <button
          key={o.label}
          type="button"
          onClick={() => onChange(o.key)}
          className={`px-2.5 py-1 rounded-md cursor-pointer border-none font-medium ${
            value === o.key ? 'bg-accent text-accent-fg' : 'bg-transparent text-muted hover:text-text'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// Houses the feed's lower-frequency display toggles (Show excluded / Show
// full name) behind one button instead of two always-visible checkboxes -
// added once the direction toggle (above) needed the same row and left no
// room to keep everything inline without wrapping to a second line on an
// ordinary window width. Same outside-click-to-close popover idiom as
// DateRangePicker.tsx.
function MoreFiltersMenu({
  excludedVisible,
  onExcludedVisibleChange,
  showFullName,
  onShowFullNameChange,
}: {
  excludedVisible: boolean
  onExcludedVisibleChange: (v: boolean) => void
  showFullName: boolean
  onShowFullNameChange: (v: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const activeCount = (excludedVisible ? 0 : 1) + (showFullName ? 1 : 0)

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onClickOutside)
    return () => window.removeEventListener('mousedown', onClickOutside)
  }, [open])

  return (
    <div className="relative shrink-0" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        title="More filters"
        className="flex items-center gap-1.5 text-xs px-2.5 py-2 rounded-lg border border-border bg-input text-muted hover:text-text cursor-pointer"
      >
        <SlidersHorizontal size={13} />
        Filters
        {activeCount > 0 && (
          <span className="w-4 h-4 rounded-full bg-accent text-accent-fg text-[10px] font-semibold flex items-center justify-center">
            {activeCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-[calc(100%+6px)] z-40 bg-card border border-border rounded-xl p-3.5 shadow-xl w-[220px] flex flex-col gap-2.5">
          <label className="flex items-center gap-2 text-xs text-text cursor-pointer">
            <Checkbox checked={excludedVisible} onChange={onExcludedVisibleChange} />
            Show excluded
          </label>
          <label
            className="flex items-center gap-2 text-xs text-text cursor-pointer"
            title="Display name is the cleaned-up label (rule/contact/AI); full name is the raw text from the bank statement"
          >
            <Checkbox checked={showFullName} onChange={onShowFullNameChange} />
            Show full name
          </label>
        </div>
      )}
    </div>
  )
}

export function Dashboard() {
  const { openDialog, hasPendingBatch } = useUploadDialog()
  const [searchParams, setSearchParams] = useSearchParams()
  // Loaded once per mount (not on every render) so a stored selection wins,
  // but doesn't keep re-overriding state after the user changes it. URL
  // query params (present when a filtered view was shared/bookmarked) win
  // over localStorage, which wins over the bare default.
  const [storedFilters] = useState(loadDashboardFilters)

  const [range, setRange] = useState<{ from: string; to: string } | undefined>(() => {
    const from = searchParams.get('from')
    const to = searchParams.get('to')
    return from && to ? { from, to } : storedFilters.range
  })
  const [accountId, setAccountId] = useState<string | undefined>(
    () => searchParams.get('account') ?? storedFilters.accountId ?? undefined,
  )
  const [excludedVisible, setExcludedVisible] = useState<boolean>(() => {
    const v = searchParams.get('excluded')
    return v != null ? v !== '0' : (storedFilters.excludedVisible ?? true)
  })
  const [showFullName, setShowFullName] = useState<boolean>(() => {
    const v = searchParams.get('full')
    return v != null ? v === '1' : (storedFilters.showFullName ?? false)
  })
  const [searchText, setSearchText] = useState(() => searchParams.get('q') ?? storedFilters.searchText ?? '')
  const [categoryFilter, setCategoryFilter] = useState(
    () => searchParams.get('category') ?? storedFilters.categoryFilter ?? '',
  )
  const [direction, setDirection] = useState<DirectionFilter | undefined>(() => {
    const v = searchParams.get('dir')
    return v === 'inflow' || v === 'outflow' ? v : storedFilters.direction
  })
  const [refundTxId, setRefundTxId] = useState<number | null>(null)
  const [editingTxId, setEditingTxId] = useState<number | null>(null)
  const toast = useToast()
  const deleteTransaction = useDeleteTransaction()
  // Optimistically-hidden rows whose real DELETE is still deferred behind
  // the undo toast - same pattern as Rules.tsx's pendingDeleteIds.
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<number>>(new Set())
  const deleteTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  useEffect(() => {
    const timers = deleteTimers
    return () => {
      for (const t of timers.current.values()) clearTimeout(t)
    }
  }, [])
  const [recategorizeOpen, setRecategorizeOpen] = useState(false)
  const [chartsTab, setChartsTab] = useState<'cashflow' | 'velocity'>('cashflow')
  const [breakdownTab, setBreakdownTab] = useState<'category' | 'merchants' | 'paynow'>('category')
  const [sort, setSort] = useState<{ field: SortField; dir: SortDir }>({ field: 'date', dir: 'desc' })
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)

  // Debounced 150ms behind searchText - typing feels instant (the input is
  // still bound to searchText directly) while the (potentially large)
  // re-filter only runs once typing pauses.
  const [debouncedSearch, setDebouncedSearch] = useState(searchText)
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(searchText), 150)
    return () => clearTimeout(t)
  }, [searchText])

  // One place that keeps localStorage and the URL query string in sync with
  // whichever filter just changed - each update* function below passes only
  // the field it owns, and every other current value is read fresh from
  // this render's closure.
  function persist(overrides: Partial<DashboardFilters>) {
    const next: DashboardFilters = {
      range,
      accountId,
      showFullName,
      searchText,
      categoryFilter,
      excludedVisible,
      direction,
      ...overrides,
    }
    saveDashboardFilters(next)
    const params = new URLSearchParams()
    if (next.range) {
      params.set('from', next.range.from)
      params.set('to', next.range.to)
    }
    if (next.accountId) params.set('account', next.accountId)
    if (next.categoryFilter) params.set('category', next.categoryFilter)
    if (next.searchText) params.set('q', next.searchText)
    if (next.excludedVisible === false) params.set('excluded', '0')
    if (next.showFullName) params.set('full', '1')
    if (next.direction) params.set('dir', next.direction)
    setSearchParams(params, { replace: true })
  }

  function updateRange(next: { from: string; to: string }) {
    setRange(next)
    persist({ range: next })
  }

  function updateAccountId(next: string | undefined) {
    setAccountId(next)
    persist({ accountId: next })
  }

  function updateShowFullName(next: boolean) {
    setShowFullName(next)
    persist({ showFullName: next })
  }

  function updateSearchText(next: string) {
    setSearchText(next)
    persist({ searchText: next })
  }

  function updateCategoryFilter(next: string) {
    setCategoryFilter(next)
    persist({ categoryFilter: next })
  }

  function updateExcludedVisible(next: boolean) {
    setExcludedVisible(next)
    persist({ excludedVisible: next })
  }

  function updateDirection(next: DirectionFilter | undefined) {
    setDirection(next)
    persist({ direction: next })
  }

  function toggleSort(field: SortField) {
    setSort((prev) => (prev.field === field ? { field, dir: prev.dir === 'asc' ? 'desc' : 'asc' } : { field, dir: 'desc' }))
  }

  // Clicking the same category again clears the filter instead of being a
  // no-op re-select - lets the donut/legend double as a toggle.
  function selectCategoryFilter(category: string) {
    const next = categoryFilter === category ? '' : category
    updateCategoryFilter(next)
    // DASH-5: the donut is above the fold but the feed it filters can be
    // well below it - without this, picking a category silently changes a
    // list the user isn't looking at.
    if (next) feedRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const accountsQ = useAccounts()
  const settingsQ = useSettings()
  // Always enabled (not gated on recategorizeOpen) so the Recategorize
  // button below can reflect a pending batch's state - AI still running, or
  // done and awaiting commit - even before the dialog is ever opened. Same
  // query key RecategorizeReviewDialog itself uses, so mounting it doesn't
  // trigger a second fetch.
  const recategorizeBatchQ = useCurrentRecategorizeBatch(true)
  // Hidden categories included (unlike rule/contact pickers) - "Others" and
  // "Other Income" are real fallback categories transactions can land in,
  // so they need to be searchable/filterable here even though they're not
  // offered as an assignment target.
  const categoriesQ = useCategories(true)
  const monthlyTotalsQ = useMonthlyTotals(accountId)

  // No stored range (a first-ever visit, or the user never picked one) -
  // default to the trailing 3 months ending at the latest month with data,
  // computed fresh every time rather than persisted, so it stays "current"
  // instead of freezing at whatever the default happened to be once.
  useEffect(() => {
    if (storedFilters.range || range) return
    const months = (monthlyTotalsQ.data ?? []).map((t) => t.month)
    if (months.length === 0) return
    const latest = months.reduce((a, b) => (a > b ? a : b))
    setRange({ from: shiftMonth(latest, -2), to: latest })
  }, [monthlyTotalsQ.data, range, storedFilters.range])

  const summaryQ = useDashboardSummary({ date_from: range?.from, date_to: range?.to, account_id: accountId })
  const resolvedRange = range ?? (summaryQ.data ? { from: summaryQ.data.date_from, to: summaryQ.data.date_to } : undefined)
  const txQ = useTransactions({
    date_from: resolvedRange?.from,
    date_to: resolvedRange?.to,
    account_id: accountId,
    include_excluded: true,
  })

  const visibleTransactions = useMemo(
    () => (txQ.data ?? []).filter((t) => (excludedVisible || !t.is_excluded) && !pendingDeleteIds.has(t.id)),
    [txQ.data, excludedVisible, pendingDeleteIds],
  )
  // DASH-7: the outflow metric card always excludes (it comes straight from
  // the server, which never counts excluded rows), while "Show excluded"
  // only changes what the feed list below renders - so turning the toggle
  // on used to add rows to the list with nothing reconciling that against
  // the card total above it. Computed from txQ.data (fetched with
  // include_excluded: true) rather than a second request.
  const excludedInRange = useMemo(() => (txQ.data ?? []).filter((t) => t.is_excluded), [txQ.data])
  const excludedTotal = useMemo(() => excludedInRange.reduce((sum, t) => sum + Math.abs(t.amount), 0), [excludedInRange])
  const filteredTransactions = useMemo(() => {
    const q = debouncedSearch.trim().toLowerCase()
    return visibleTransactions.filter((t) => {
      if (categoryFilter && t.category !== categoryFilter) return false
      if (direction === 'inflow' && t.amount <= 0) return false
      if (direction === 'outflow' && t.amount > 0) return false
      if (q) {
        const haystack = `${t.matched_label ?? ''} ${t.raw_description} ${t.category} ${t.bank_name} ${
          t.account_number_masked
        } ${fmtPlain(Math.abs(t.amount))}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [visibleTransactions, debouncedSearch, categoryFilter, direction])

  const sortedTransactions = useMemo(() => {
    const list = [...filteredTransactions]
    const dir = sort.dir === 'asc' ? 1 : -1
    list.sort((a, b) => {
      if (sort.field === 'amount') return dir * (a.amount - b.amount)
      return dir * a.transaction_date.localeCompare(b.transaction_date)
    })
    return list
  }, [filteredTransactions, sort])

  // Reset pagination whenever the filtered/sorted set changes underneath it
  // - otherwise "visibleCount" from a previous, larger result set would
  // silently show more rows than a "Load more" click ever asked for.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [debouncedSearch, categoryFilter, direction, excludedVisible, range, accountId, sort])

  const pagedTransactions = sortedTransactions.slice(0, visibleCount)

  // Per-month count/outflow, for the sticky month-divider rows below - only
  // meaningful (and only rendered) while sorted by date, since any other
  // sort scatters a month's rows across the list.
  const monthAggregates = useMemo(() => {
    const map = new Map<string, { count: number; outflow: number }>()
    for (const t of filteredTransactions) {
      const key = t.transaction_date.slice(0, 7)
      const agg = map.get(key) ?? { count: 0, outflow: 0 }
      agg.count += 1
      if (t.amount < 0) agg.outflow += -t.amount
      map.set(key, agg)
    }
    return map
  }, [filteredTransactions])

  const netTotal = useMemo(() => filteredTransactions.reduce((sum, t) => sum + t.amount, 0), [filteredTransactions])
  // Excluded rows are left out on purpose: this hint sits under Total
  // Inflow, which the backend computes from non-excluded rows only
  // (routers/dashboard.py::_fetch_range_transactions). Counting every
  // positive row here made the two disagree the moment anything inflow-side
  // got excluded - a card statement's bill-payment credits, say.
  const inflowCount = (txQ.data ?? []).filter((t) => t.amount > 0 && !t.is_excluded).length
  const maxAbsAmount = useMemo(
    () => filteredTransactions.reduce((m, t) => Math.max(m, Math.abs(t.amount)), 0),
    [filteredTransactions],
  )

  // The column header for a divider row needs its own height to stick
  // *below* the divider, not under it - measured once (it's a static
  // single-line row, no resize listener needed).
  const columnHeaderRef = useRef<HTMLDivElement>(null)
  const [columnHeaderHeight, setColumnHeaderHeight] = useState(0)
  // Scroll target for selectCategoryFilter (DASH-5) - the feed card itself,
  // not the row list inside it, so the card's own header/filter chips come
  // into view too, not just a blank first row.
  const feedRef = useRef<HTMLDivElement>(null)
  // Layout effect, not a plain effect - runs before the browser paints, so
  // the very first divider (if one's visible without scrolling) never
  // flashes at top:0 overlapping the column header for a frame.
  useLayoutEffect(() => {
    if (columnHeaderRef.current) setColumnHeaderHeight(columnHeaderRef.current.offsetHeight)
  }, [])

  // Checked before the loading gate below: without this, a failed first
  // fetch has isLoading:false and no data, which used to fall straight into
  // the "Loading dashboard…" sentence forever - "no data yet" and "the
  // backend is down" looked identical (X-4 in UI Review.dc.html).
  if (summaryQ.isError || accountsQ.isError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <ErrorState
          description="Couldn't load the dashboard."
          onRetry={() => {
            summaryQ.refetch()
            accountsQ.refetch()
          }}
        />
      </div>
    )
  }

  // Only true on the very first load - there's genuinely nothing to render
  // yet. A range/account change no longer lands here: useDashboardSummary's
  // placeholderData: keepPreviousData keeps summaryQ.data (and isLoading
  // false) across a query-key change, so the page stays mounted and
  // `isRefreshing` below is what signals an in-flight update instead. This
  // used to also fire on every filter change (root cause 03 / DASH-1 in
  // UI Review.dc.html), replacing the whole dashboard with this sentence.
  if (summaryQ.isLoading || !summaryQ.data || accountsQ.isLoading) {
    return (
      <div className="p-9">
        <div className="text-muted">Loading dashboard…</div>
      </div>
    )
  }

  if ((accountsQ.data ?? []).length === 0) {
    return (
      <div className="min-h-screen flex flex-col p-9">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <div className="w-13 h-13 rounded-xl bg-accent/12 mx-auto mb-5 flex items-center justify-center">
              <FileUp size={22} className="text-accent" />
            </div>
            <div className="text-xl font-semibold text-text mb-2.5">No statements yet</div>
            <div className="text-md text-muted mb-5.5">
              Upload {bankListLabel(settingsQ.data?.supported_banks ?? [])} e-statement PDF to see your spending
              here — or drag one in anywhere.
            </div>
            <Button variant="primary" onClick={openDialog} disabled={hasPendingBatch}>
              + Upload Bank Statement
            </Button>
          </div>
        </div>
      </div>
    )
  }

  const s = summaryQ.data
  const rangeLabel = fmtMonthRangeLabel(s.date_from, s.date_to)
  const rangeMonthCount = s.cash_flow.length
  const topCategory = s.category_breakdown[0]
  const prevRangeFrom = shiftMonth(s.date_from, -rangeMonthCount)
  const prevRangeTo = shiftMonth(s.date_to, -rangeMonthCount)
  const lastVelocity = s.spend_velocity[s.spend_velocity.length - 1]
  const effectiveRange = resolvedRange ?? { from: s.date_from, to: s.date_to }
  const spansMultipleYears = effectiveRange.from.slice(0, 4) !== effectiveRange.to.slice(0, 4)

  function openEditor(tx: Transaction) {
    setEditingTxId((prev) => (prev === tx.id ? null : tx.id))
  }

  // Removes the row immediately and shows an undo toast; the real DELETE
  // only fires once the undo window passes - see Rules.tsx's identical
  // handleDelete, which this mirrors.
  function handleDeleteTransaction(tx: Transaction) {
    if (editingTxId === tx.id) setEditingTxId(null)
    setPendingDeleteIds((prev) => new Set(prev).add(tx.id))
    const timer = setTimeout(() => {
      deleteTimers.current.delete(tx.id)
      deleteTransaction.mutate(tx.id, {
        onError: () => {
          setPendingDeleteIds((prev) => {
            const next = new Set(prev)
            next.delete(tx.id)
            return next
          })
        },
      })
    }, DELETE_UNDO_MS)
    deleteTimers.current.set(tx.id, timer)
    toast.success(`Transaction deleted — "${tx.matched_label ?? tx.raw_description}"`, {
      durationMs: DELETE_UNDO_MS,
      action: {
        label: 'Undo',
        onClick: () => {
          clearTimeout(deleteTimers.current.get(tx.id))
          deleteTimers.current.delete(tx.id)
          setPendingDeleteIds((prev) => {
            const next = new Set(prev)
            next.delete(tx.id)
            return next
          })
        },
      },
    })
  }

  // A background refetch (filter changed, or a stale query refetched on
  // remount) while data from a previous fetch is still on screen - distinct
  // from the true first-ever load below, which has nothing to show yet.
  // keepPreviousData on useDashboardSummary/useTransactions means isLoading
  // no longer flips true on every range/account change (root cause 03 /
  // DASH-1), so this is the only signal left that something's updating.
  const isRefreshing = !summaryQ.isLoading && (summaryQ.isFetching || txQ.isFetching)

  return (
    <div className="px-9 pb-15">
      <div className="sticky top-0 z-20 -mx-9 px-9 bg-bg pt-7 pb-5.5 relative">
        <div
          className={`absolute bottom-0 left-0 right-0 h-[2px] bg-accent transition-opacity duration-200 ${isRefreshing ? 'opacity-100' : 'opacity-0'}`}
        />
        <div className="flex items-start justify-between gap-4 flex-wrap">
          {/* Same title+icon shape PageShell renders for every other page - this
              header stays hand-rolled only because it's sticky with its own
              scroll-tinted background and filter row, not because it looks
              different. Keep the two in sync. */}
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-accent/12 flex items-center justify-center shrink-0">
              <LayoutGrid size={18} className="text-accent" />
            </div>
            <div className="min-w-0">
              <div className="text-title font-bold font-display">Dashboard</div>
              <div className="text-md text-muted mt-0.5">Post-mortem view of where the money went</div>
            </div>
          </div>
          <div className="flex gap-2.5 items-center">
            <DateRangePicker
              value={effectiveRange}
              onChange={updateRange}
              monthlyTotals={monthlyTotalsQ.data ?? []}
            />
            <Select value={accountId ?? ''} onChange={(e) => updateAccountId(e.target.value || undefined)} className="w-[190px]">
              <option value="">All Accounts</option>
              {(accountsQ.data ?? []).map((a) => (
                <option key={a.id} value={a.id}>
                  {a.bank_name} {a.account_number_masked}
                </option>
              ))}
            </Select>
            {recategorizeBatchQ.data?.ai_status === 'running' ? (
              <Button
                size="sm"
                onClick={() => setRecategorizeOpen(true)}
                title="AI is still categorizing the proposed changes - click to view progress"
                className="flex items-center gap-1.5"
                style={{ background: 'var(--color-ai-surface)', color: 'var(--color-ai-text)', border: 'none' }}
              >
                <Loader2 size={14} className="animate-spin" />
                AI categorizing…
                {recategorizeBatchQ.data.ai_started_at && (
                  <ElapsedTimer startedAt={recategorizeBatchQ.data.ai_started_at} />
                )}
              </Button>
            ) : recategorizeBatchQ.data ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setRecategorizeOpen(true)}
                title="A recategorize run is proposed and awaiting your review"
                className="flex items-center gap-1.5"
              >
                <RefreshCw size={14} />
                Recategorize · {recategorizeBatchQ.data.changed} awaiting commit
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => setRecategorizeOpen(true)}
                title="Re-run categorization rules over the selected range"
                className="flex items-center gap-1.5"
              >
                <RefreshCw size={14} />
                Recategorize
              </Button>
            )}
          </div>
        </div>
      </div>

      {recategorizeOpen && (
        <RecategorizeReviewDialog
          range={{ from: s.date_from, to: s.date_to }}
          accountId={accountId}
          onClose={() => setRecategorizeOpen(false)}
        />
      )}

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-3.5 mb-5">
        <MetricCard
          label="Total Inflow"
          value={fmtPlain(s.metrics.total_inflow)}
          valueClassName="text-success"
          hint={`${inflowCount} inflow transaction${inflowCount === 1 ? '' : 's'}`}
        />
        <MetricCard
          label="Total Outflow"
          value={fmtPlain(s.metrics.total_outflow)}
          valueClassName="text-danger-text"
          delta={
            lastVelocity ? (
              <OutflowDelta
                current={lastVelocity.current_period_cumulative}
                previous={lastVelocity.previous_period_cumulative}
                prevLabel={fmtMonthRangeLabel(prevRangeFrom, prevRangeTo)}
              />
            ) : undefined
          }
          hint={
            excludedInRange.length > 0
              ? `${fmtPlain(excludedTotal)} excluded · ${excludedInRange.length} transaction${excludedInRange.length === 1 ? '' : 's'} not counted`
              : undefined
          }
        />
        <MetricCard
          label="Net Expenditure"
          value={fmtPlain(s.metrics.net_expenditure)}
          hint={`over ${rangeMonthCount} month${rangeMonthCount === 1 ? '' : 's'}`}
        />
        <MetricCard
          label="Top Category"
          variant="text"
          value={topCategory ? topCategory.category : '—'}
          delta={topCategory ? <div className="text-xs text-accent mt-1">{topCategory.pct}% of outflow</div> : undefined}
          hint={topCategory ? fmtPlain(topCategory.amount) : 'No spending yet'}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-3.5 mb-5">
        {/* min-h matches the breakdown card alongside it (DASH-4) - without
            it, this card's height tracked whichever tab's content was
            taller (CashFlowChart's fixed-height bars vs VelocityChart's
            fixed-height svg + a legend row that can wrap), so switching
            tabs visibly resized the card. */}
        <Card className="min-h-[268px]">
          <Tabs
            tabs={[
              { key: 'cashflow', label: 'Cash Flow' },
              { key: 'velocity', label: 'Spend Velocity' },
            ]}
            active={chartsTab}
            onChange={setChartsTab}
            right={chartsTab === 'cashflow' ? cashFlowQualifier(s.cash_flow, monthlyTotalsQ.data) : 'cumulative pace'}
          />
          {chartsTab === 'cashflow' ? (
            <CashFlowChart data={s.cash_flow} trend={monthlyTotalsQ.data} rangeFrom={s.date_from} rangeTo={s.date_to} bare />
          ) : (
            <VelocityChart
              data={s.spend_velocity}
              periodLabel={rangeLabel}
              prevPeriodLabel={fmtMonthRangeLabel(prevRangeFrom, prevRangeTo)}
              bare
            />
          )}
        </Card>

        {/* DASH-4: a shared min-height so switching Category/Merchants/
            PayNow doesn't resize the card - Merchants/PayNow used to be a
            handful of unpadded text rows with no fixed height. */}
        <Card className="min-h-[268px]">
          <Tabs
            tabs={[
              { key: 'category', label: 'Category Breakdown' },
              { key: 'merchants', label: 'Top Merchants' },
              { key: 'paynow', label: 'Top Paynow Contacts' },
            ]}
            active={breakdownTab}
            onChange={setBreakdownTab}
          />
          {breakdownTab === 'category' && (
            <CategoryDonut
              data={s.category_breakdown}
              categories={categoriesQ.data}
              onCategoryClick={selectCategoryFilter}
              selectedCategory={categoryFilter || undefined}
              bare
            />
          )}
          {breakdownTab === 'merchants' && (
            <div className="flex flex-col">
              {s.top_merchants.length === 0 && <div className="text-xs text-muted-2 py-1">No spending yet</div>}
              {s.top_merchants.map((m) => (
                <RankedBarRow key={m.name} entry={m} maxAmount={s.top_merchants[0]?.amount ?? 0} />
              ))}
            </div>
          )}
          {breakdownTab === 'paynow' && (
            <div className="flex flex-col">
              {s.top_paynow_contacts.length === 0 && <div className="text-xs text-muted-2 py-1">No PayNow transfers yet</div>}
              {s.top_paynow_contacts.map((p) => (
                <RankedBarRow key={p.name} entry={p} maxAmount={s.top_paynow_contacts[0]?.amount ?? 0} />
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Transaction feed */}
      <Card ref={feedRef} padding="" className="overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border gap-3 flex-wrap">
          <div className="text-md font-semibold font-display shrink-0">
            Transaction Feed
            <span className="text-muted-2 font-normal ml-1.5">
              · Showing {pagedTransactions.length} of {filteredTransactions.length}
            </span>
          </div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <Input
              fullWidth={false}
              value={searchText}
              onChange={(e) => updateSearchText(e.target.value)}
              placeholder="Search transactions…"
              className="w-[200px]"
            />
            <Select
              uiSize="sm"
              value={categoryFilter}
              onChange={(e) => updateCategoryFilter(e.target.value)}
              className="w-[160px]"
            >
              <option value="">All Categories</option>
              {categoryOptionElements(categoriesQ.data)}
            </Select>
            <DirectionToggle value={direction} onChange={updateDirection} />
            <MoreFiltersMenu
              excludedVisible={excludedVisible}
              onExcludedVisibleChange={updateExcludedVisible}
              showFullName={showFullName}
              onShowFullNameChange={updateShowFullName}
            />
          </div>
        </div>

        {/* Active-filter chips - category/search/direction are otherwise
            invisible once set (the category select can be scrolled out of
            view, and a donut-slice click sets it with no on-screen trace at
            all). */}
        {(categoryFilter || searchText || direction) && (
          <div className="flex items-center gap-2 px-5 py-2 border-b border-divider flex-wrap">
            {categoryFilter && (
              <button
                onClick={() => updateCategoryFilter('')}
                className="inline-flex items-center gap-1.5 text-2xs px-2.5 py-1 rounded-full bg-input border border-border text-text hover:border-accent cursor-pointer"
              >
                Category:
                <CategoryLabel category={categoryFilter} categories={categoriesQ.data} size={11} tinted />
                <span aria-hidden>×</span>
              </button>
            )}
            {direction && (
              <button
                onClick={() => updateDirection(undefined)}
                className="inline-flex items-center gap-1.5 text-2xs px-2.5 py-1 rounded-full bg-input border border-border text-text hover:border-accent cursor-pointer"
              >
                {direction === 'inflow' ? 'Inflow only' : 'Outflow only'} <span aria-hidden>×</span>
              </button>
            )}
            {searchText && (
              <button
                onClick={() => updateSearchText('')}
                className="inline-flex items-center gap-1.5 text-2xs px-2.5 py-1 rounded-full bg-input border border-border text-text hover:border-accent cursor-pointer"
              >
                Search: "{searchText}" <span aria-hidden>×</span>
              </button>
            )}
            {(categoryFilter ? 1 : 0) + (direction ? 1 : 0) + (searchText ? 1 : 0) > 1 && (
              <button
                onClick={() => {
                  updateCategoryFilter('')
                  updateDirection(undefined)
                  updateSearchText('')
                }}
                className="text-2xs text-muted-2 hover:text-text underline cursor-pointer bg-transparent border-none p-0"
              >
                Clear all
              </button>
            )}
          </div>
        )}

        {/* Bounded, independently-scrolling region - this is what lets the
            column header below stick at top:0 without needing to measure
            the page-level header's height, and keeps an all-time range's
            1000+ rows from turning the whole page into one giant scroller. */}
        <div className="max-h-[65vh] overflow-y-auto">
          <DataTableHeader
            headerRef={columnHeaderRef}
            columns={FEED_COLUMNS}
            gridTemplate={FEED_GRID_TEMPLATE}
            sort={sort}
            onSort={toggleSort}
            className="px-5 py-2.5 border-b border-divider sticky top-0 z-10 bg-card text-2xs text-muted-2 uppercase tracking-wide"
          />
          {txQ.isLoading && <div className="p-5 text-muted text-sm">Loading transactions…</div>}
          {txQ.isError && <ErrorState description="Couldn't load transactions for this range." onRetry={() => txQ.refetch()} />}
          {txQ.isSuccess && filteredTransactions.length === 0 && (
            <EmptyState
              icon={searchText || categoryFilter || direction ? SearchX : Receipt}
              title={
                searchText || categoryFilter || direction
                  ? 'No transactions match your filters'
                  : 'No transactions for this range yet'
              }
              description={
                searchText || categoryFilter || direction
                  ? 'Try a different search term, category, or direction.'
                  : 'Pick a different date range, or upload a statement to get started.'
              }
              action={
                searchText || categoryFilter || direction ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      updateSearchText('')
                      updateCategoryFilter('')
                      updateDirection(undefined)
                    }}
                  >
                    Clear filters
                  </Button>
                ) : undefined
              }
            />
          )}
          {(() => {
            let lastMonthKey: string | null = null
            return pagedTransactions.map((tx) => {
              const monthKey = tx.transaction_date.slice(0, 7)
              const showDivider = sort.field === 'date' && monthKey !== lastMonthKey
              lastMonthKey = monthKey
              const agg = monthAggregates.get(monthKey)
              const primaryText = showFullName ? tx.raw_description : (tx.matched_label ?? tx.raw_description)
              const isHeavy = maxAbsAmount > 0 && Math.abs(tx.amount) >= maxAbsAmount * 0.5

              return (
                <div key={tx.id}>
                  {showDivider && (
                    <div
                      className="sticky z-[5] px-5 py-1.5 text-2xs font-semibold text-muted-2 bg-input border-b border-divider"
                      style={{ top: columnHeaderHeight }}
                    >
                      {fmtMonthYearLabel(monthKey)} · {agg?.count ?? 0} transaction{(agg?.count ?? 0) === 1 ? '' : 's'} ·{' '}
                      {fmtPlain(agg?.outflow ?? 0)} out
                    </div>
                  )}
                  <div
                    role="button"
                    tabIndex={0}
                    onClick={() => openEditor(tx)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        openEditor(tx)
                      }
                    }}
                    className="grid items-center px-5 py-3 text-md border-b border-divider group cursor-pointer hover:bg-input/50 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent"
                    style={{ gridTemplateColumns: FEED_GRID_TEMPLATE, opacity: tx.is_excluded ? 0.5 : 1 }}
                  >
                    <div className="text-muted font-mono text-xs">{fmtDate(tx.transaction_date, { withYear: spansMultipleYears })}</div>
                    <div className="min-w-0 pr-2">
                      <div className="truncate" title={tx.raw_description}>
                        {highlightMatch(primaryText, debouncedSearch)}
                        {tx.is_excluded && (
                          <span className="text-[10px] text-muted-2 border border-border rounded px-1.5 py-0.5 ml-1.5">
                            excluded
                          </span>
                        )}
                      </div>
                      {/* Full-name mode surfaces the cleaned-up label as a second line
                          underneath the raw text - display-name mode (the default,
                          unchanged from before this toggle existed) stays single-line,
                          with the raw text still reachable via the title tooltip. */}
                      {showFullName && tx.matched_label && (
                        <div className="truncate text-2xs text-muted-2">{tx.matched_label}</div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <CategoryBadge category={tx.category} categories={categoriesQ.data} />
                    </div>
                    <div className="text-muted text-xs truncate">
                      {tx.bank_name} {tx.account_number_masked}
                    </div>
                    <div
                      className={`text-right font-mono ${tx.amount > 0 ? 'text-success' : 'text-text'} ${
                        isHeavy ? 'font-semibold' : ''
                      }`}
                    >
                      {fmtSigned(tx.amount)}
                    </div>
                    <div className="text-center">
                      {tx.has_refund_link && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            setRefundTxId(tx.id)
                          }}
                          title="View refund pairing"
                          className="border-none bg-transparent cursor-pointer text-accent text-base"
                        >
                          ⇄
                        </button>
                      )}
                    </div>
                    <div className="flex items-center justify-center gap-2.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          openEditor(tx)
                        }}
                        title="Edit transaction"
                        className="border-none bg-transparent cursor-pointer text-muted-2 hover:text-text opacity-40 group-hover:opacity-100 group-focus-within:opacity-100"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteTransaction(tx)
                        }}
                        title="Delete transaction"
                        className="border-none bg-transparent cursor-pointer text-muted-2 hover:text-danger-text opacity-40 group-hover:opacity-100 group-focus-within:opacity-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  {editingTxId === tx.id && (
                    <TransactionEditPopover transaction={tx} onClose={() => setEditingTxId(null)} />
                  )}
                </div>
              )
            })
          })()}
          {visibleCount < filteredTransactions.length && (
            <button
              onClick={() => setVisibleCount((v) => v + PAGE_SIZE)}
              className="w-full text-xs font-semibold text-muted hover:text-text px-5 py-3 border-b border-divider bg-transparent cursor-pointer"
            >
              Load more ({filteredTransactions.length - visibleCount} remaining)
            </button>
          )}
        </div>

        {filteredTransactions.length > 0 && (
          <div className="flex items-center justify-between px-5 py-2.5 text-xs text-muted border-t border-border">
            <div>
              {filteredTransactions.length} transaction{filteredTransactions.length === 1 ? '' : 's'} in view
            </div>
            <div className={`font-mono font-semibold ${netTotal > 0 ? 'text-success' : 'text-text'}`}>
              Net {fmtSigned(netTotal)}
            </div>
          </div>
        )}
      </Card>

      {refundTxId != null && <RefundDrawer transactionId={refundTxId} onClose={() => setRefundTxId(null)} />}
    </div>
  )
}
