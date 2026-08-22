import { FileUp, Pencil, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useAccounts, useCategories, useDashboardSummary, useMonthlyTotals, useTransactions } from '../api/hooks'
import { amountIntensityColor, fmtDate, fmtMonthRangeLabel, fmtPlain, shiftMonth } from '../lib/format'
import { loadDashboardFilters, saveDashboardFilters } from '../lib/dashboardFilters'
import { CashFlowChart } from '../components/CashFlowChart'
import { CategoryBadge } from '../components/CategoryBadge'
import { categoryOptionElements } from '../components/CategoryOptions'
import { CategoryDonut } from '../components/CategoryDonut'
import { VelocityChart } from '../components/VelocityChart'
import { RefundDrawer } from '../components/RefundDrawer'
import { DateRangePicker } from '../components/DateRangePicker'
import { TransactionEditPopover } from '../components/TransactionEditPopover'
import { RecategorizeReviewDialog } from '../components/RecategorizeReviewDialog'
import { Checkbox } from '../components/Checkbox'
import { Select } from '../components/Select'
import { Tabs } from '../components/Tabs'
import { useUploadDialog } from '../components/UploadProvider'

function MetricCard({
  label,
  value,
  valueClassName = '',
  hint,
}: {
  label: string
  value: string
  valueClassName?: string
  hint?: string
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-4.5">
      <div className="text-xs text-muted mb-2">{label}</div>
      <div className={`text-2xl font-bold font-mono ${valueClassName}`}>{value}</div>
      {hint && <div className="text-xs text-muted-2 mt-1">{hint}</div>}
    </div>
  )
}

export function Dashboard() {
  const { openDialog, hasPendingBatch } = useUploadDialog()
  // Loaded once per mount (not on every render) so a stored selection wins,
  // but doesn't keep re-overriding state after the user changes it.
  const [storedFilters] = useState(loadDashboardFilters)
  const [range, setRange] = useState<{ from: string; to: string } | undefined>(storedFilters.range)
  const [accountId, setAccountId] = useState<string | undefined>(storedFilters.accountId)
  const [excludedVisible, setExcludedVisible] = useState(true)
  const [searchText, setSearchText] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [refundTxId, setRefundTxId] = useState<number | null>(null)
  const [editingTxId, setEditingTxId] = useState<number | null>(null)
  const [recategorizeOpen, setRecategorizeOpen] = useState(false)
  const [chartsTab, setChartsTab] = useState<'cashflow' | 'velocity'>('cashflow')
  const [breakdownTab, setBreakdownTab] = useState<'category' | 'merchants' | 'paynow'>('category')

  // Clicking the same category again clears the filter instead of being a
  // no-op re-select - lets the donut/legend double as a toggle.
  function selectCategoryFilter(category: string) {
    setCategoryFilter((prev) => (prev === category ? '' : category))
  }

  const accountsQ = useAccounts()
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

  function updateRange(next: { from: string; to: string }) {
    setRange(next)
    saveDashboardFilters({ range: next, accountId })
  }

  function updateAccountId(next: string | undefined) {
    setAccountId(next)
    saveDashboardFilters({ range, accountId: next })
  }

  const summaryQ = useDashboardSummary({ date_from: range?.from, date_to: range?.to, account_id: accountId })
  const resolvedRange = range ?? (summaryQ.data ? { from: summaryQ.data.date_from, to: summaryQ.data.date_to } : undefined)
  const txQ = useTransactions({
    date_from: resolvedRange?.from,
    date_to: resolvedRange?.to,
    account_id: accountId,
    include_excluded: true,
  })

  const visibleTransactions = useMemo(
    () => (txQ.data ?? []).filter((t) => excludedVisible || !t.is_excluded),
    [txQ.data, excludedVisible],
  )
  const filteredTransactions = useMemo(() => {
    const q = searchText.trim().toLowerCase()
    return visibleTransactions.filter((t) => {
      if (categoryFilter && t.category !== categoryFilter) return false
      if (q) {
        const haystack = `${t.matched_label ?? ''} ${t.raw_description}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [visibleTransactions, searchText, categoryFilter])
  const inflowCount = (txQ.data ?? []).filter((t) => t.amount > 0).length
  const maxAbsAmount = useMemo(
    () => filteredTransactions.reduce((m, t) => Math.max(m, Math.abs(t.amount)), 0),
    [filteredTransactions],
  )
  const distinctAccounts = new Set((txQ.data ?? []).map((t) => t.account_id)).size

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
            <div className="text-[13px] text-muted mb-5.5">
              Upload a DBS, OCBC, or UOB e-statement PDF to see your spending here — or drag one in anywhere.
            </div>
            <button
              onClick={openDialog}
              disabled={hasPendingBatch}
              className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              + Upload Bank Statement
            </button>
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

  return (
    <div className="px-9 pb-15">
      <div className="sticky top-0 z-20 -mx-9 px-9 bg-bg pt-7 pb-5.5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-[22px] font-bold font-display">Dashboard</div>
            <div className="text-[13px] text-muted mt-0.5">Post-mortem view of where the money went</div>
          </div>
          <div className="flex gap-2.5 items-center">
            <DateRangePicker
              value={resolvedRange ?? { from: s.date_from, to: s.date_to }}
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
            <button
              onClick={() => setRecategorizeOpen(true)}
              title="Re-run categorization rules over the selected range"
              className="flex items-center gap-1.5 text-[13px] px-3 py-2 rounded-lg border border-border bg-input text-text cursor-pointer"
            >
              <RefreshCw size={14} />
              Recategorize
            </button>
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
          hint={`across ${distinctAccounts} account${distinctAccounts === 1 ? '' : 's'}`}
        />
        <MetricCard
          label="Net Expenditure"
          value={fmtPlain(s.metrics.net_expenditure)}
          hint={`over ${rangeMonthCount} month${rangeMonthCount === 1 ? '' : 's'}`}
        />
        <MetricCard
          label="Top Category"
          value={topCategory ? topCategory.category : '—'}
          hint={topCategory ? `${fmtPlain(topCategory.amount)} · ${topCategory.pct}% of outflow` : 'No spending yet'}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-3.5 mb-5">
        <div className="bg-card border border-border rounded-xl p-5">
          <Tabs
            tabs={[
              { key: 'cashflow', label: 'Cash Flow' },
              { key: 'velocity', label: 'Spend Velocity' },
            ]}
            active={chartsTab}
            onChange={setChartsTab}
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
        </div>

        <div className="bg-card border border-border rounded-xl p-5">
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
              bare
            />
          )}
          {breakdownTab === 'merchants' && (
            <>
              {s.top_merchants.length === 0 && <div className="text-xs text-muted-2 py-1">No spending yet</div>}
              {s.top_merchants.map((m) => (
                <div key={m.name} className="flex justify-between text-[13px] py-1.5 border-b border-divider">
                  <span>{m.name}</span>
                  <span className="font-mono text-text-2">{fmtPlain(m.amount)}</span>
                </div>
              ))}
            </>
          )}
          {breakdownTab === 'paynow' && (
            <>
              {s.top_paynow_contacts.length === 0 && <div className="text-xs text-muted-2 py-1">No PayNow transfers yet</div>}
              {s.top_paynow_contacts.map((p) => (
                <div key={p.name} className="flex justify-between text-[13px] py-1.5 border-b border-divider">
                  <span>{p.name}</span>
                  <span className="font-mono text-text-2">{fmtPlain(p.amount)}</span>
                </div>
              ))}
            </>
          )}
        </div>
      </div>

      {/* Transaction feed */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border gap-3 flex-wrap">
          <div className="text-[13px] font-semibold shrink-0">Transaction Feed</div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <input
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Search transactions…"
              className="text-[13px] px-3 py-1.5 rounded-lg border border-border bg-input text-text w-[200px]"
            />
            <Select
              uiSize="sm"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-[160px]"
            >
              <option value="">All Categories</option>
              {categoryOptionElements(categoriesQ.data)}
            </Select>
            <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer whitespace-nowrap">
              <Checkbox checked={excludedVisible} onChange={setExcludedVisible} />
              Show excluded
            </label>
          </div>
        </div>
        <div className="grid grid-cols-[80px_1fr_140px_130px_110px_30px_30px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-divider">
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div>Account</div>
          <div className="text-right">Amount</div>
          <div />
          <div />
        </div>
        {txQ.isLoading && <div className="p-5 text-muted text-sm">Loading transactions…</div>}
        {!txQ.isLoading && filteredTransactions.length === 0 && (
          <div className="p-5 text-muted text-sm">
            {searchText || categoryFilter ? 'No transactions match your filters.' : 'No transactions for this range yet.'}
          </div>
        )}
        {filteredTransactions.map((tx) => {
          return (
            <div key={tx.id}>
              <div
                className="grid grid-cols-[80px_1fr_140px_130px_110px_30px_30px] items-center px-5 py-3 text-[13px] border-b border-divider group"
                style={{ opacity: tx.is_excluded ? 0.5 : 1 }}
              >
                <div className="text-muted font-mono text-xs">{fmtDate(tx.transaction_date)}</div>
                <div className="truncate pr-2" title={tx.raw_description}>
                  {tx.matched_label ?? tx.raw_description}
                  {tx.is_excluded && (
                    <span className="text-[10px] text-muted-2 border border-border rounded px-1.5 py-0.5 ml-1.5">
                      excluded
                    </span>
                  )}
                </div>
                <div>
                  <CategoryBadge category={tx.category} categories={categoriesQ.data} />
                </div>
                <div className="text-muted text-xs">
                  {tx.bank_name} {tx.account_number_masked}
                </div>
                <div
                  className="text-right font-mono"
                  style={{ color: amountIntensityColor(tx.amount, maxAbsAmount) }}
                >
                  {fmtPlain(Math.abs(tx.amount))}
                </div>
                <div className="text-center">
                  {tx.has_refund_link && (
                    <button
                      onClick={() => setRefundTxId(tx.id)}
                      title="View refund pairing"
                      className="border-none bg-transparent cursor-pointer text-accent text-base"
                    >
                      ⇄
                    </button>
                  )}
                </div>
                <div className="text-center">
                  <button
                    onClick={() => setEditingTxId(editingTxId === tx.id ? null : tx.id)}
                    title="Edit transaction"
                    className="border-none bg-transparent cursor-pointer text-muted-2 hover:text-text opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
                  >
                    <Pencil size={14} />
                  </button>
                </div>
              </div>
              {editingTxId === tx.id && (
                <TransactionEditPopover transaction={tx} onClose={() => setEditingTxId(null)} />
              )}
            </div>
          )
        })}
      </div>

      {refundTxId != null && <RefundDrawer transactionId={refundTxId} onClose={() => setRefundTxId(null)} />}
    </div>
  )
}
