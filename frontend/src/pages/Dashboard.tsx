import { Pencil, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useAccounts, useCategories, useDashboardSummary, useMonthlyTotals, useTransactions } from '../api/hooks'
import { categoryColor } from '../lib/categoryColor'
import { amountIntensityColor, fmtDate, fmtMonthRangeLabel, fmtMonthYearLabel, fmtPlain, shiftMonth } from '../lib/format'
import { CashFlowChart } from '../components/CashFlowChart'
import { CategoryDonut } from '../components/CategoryDonut'
import { VelocityChart } from '../components/VelocityChart'
import { RefundDrawer } from '../components/RefundDrawer'
import { DateRangePicker } from '../components/DateRangePicker'
import { TransactionEditPopover } from '../components/TransactionEditPopover'
import { RecategorizeModal } from '../components/RecategorizeModal'
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
  const { openDialog, hasPendingBatch, openReview } = useUploadDialog()
  const [range, setRange] = useState<{ from: string; to: string } | undefined>(undefined)
  const [accountId, setAccountId] = useState<string | undefined>(undefined)
  const [excludedVisible, setExcludedVisible] = useState(true)
  const [searchText, setSearchText] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [refundTxId, setRefundTxId] = useState<number | null>(null)
  const [editingTxId, setEditingTxId] = useState<number | null>(null)
  const [recategorizeOpen, setRecategorizeOpen] = useState(false)

  const accountsQ = useAccounts()
  const categoriesQ = useCategories()
  const monthlyTotalsQ = useMonthlyTotals(accountId)
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

  const banner = hasPendingBatch && (
    <div
      className="flex items-center justify-between gap-4 px-4.5 py-3 mb-5 rounded-xl border"
      style={{ background: 'oklch(24% 0.05 70)', borderColor: 'oklch(40% 0.08 70)' }}
    >
      <div className="text-[13px]" style={{ color: 'oklch(85% 0.12 70)' }}>
        A statement is awaiting review before it can be committed.
      </div>
      <button
        onClick={openReview}
        className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer shrink-0"
      >
        Review Now
      </button>
    </div>
  )

  if (summaryQ.isLoading || !summaryQ.data || accountsQ.isLoading) {
    return (
      <div className="p-9">
        {banner}
        <div className="text-muted">Loading dashboard…</div>
      </div>
    )
  }

  if ((accountsQ.data ?? []).length === 0) {
    return (
      <div className="min-h-screen flex flex-col p-9">
        {banner}
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center max-w-md">
            <div className="w-13 h-13 rounded-xl bg-accent/12 mx-auto mb-5 flex items-center justify-center">
              <svg width="22" height="22" viewBox="0 0 16 16">
                <path d="M8 11 V2" stroke="#e35fd0" strokeWidth="1.6" fill="none" />
                <polygon points="4.5,5.5 11.5,5.5 8,1.5" fill="#e35fd0" />
                <rect x="2" y="12.5" width="12" height="2" fill="none" stroke="#e35fd0" strokeWidth="1.6" />
              </svg>
            </div>
            <div className="text-xl font-semibold text-text mb-2.5">No statements yet</div>
            <div className="text-[13px] text-muted mb-5.5">
              Upload a DBS, OCBC, or UOB e-statement PDF to see your spending here - or drag one in anywhere.
            </div>
            <button
              onClick={openDialog}
              disabled={hasPendingBatch}
              className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
            >
              + Upload Statement
            </button>
          </div>
        </div>
      </div>
    )
  }

  const s = summaryQ.data
  const rangeLabel = fmtMonthRangeLabel(s.date_from, s.date_to)
  const rangeMonthCount = s.cash_flow.length
  const showVelocity = s.spend_velocity.length > 0
  const topCategory = s.category_breakdown[0]

  return (
    <div className="px-9 pt-7 pb-15">
      {banner}
      <div className="flex items-start justify-between mb-5.5 gap-4 flex-wrap">
        <div>
          <div className="text-[22px] font-bold">Dashboard</div>
          <div className="text-[13px] text-muted mt-0.5">Post-mortem view of where the money went</div>
        </div>
        <div className="flex gap-2.5 items-center">
          <DateRangePicker
            value={resolvedRange ?? { from: s.date_from, to: s.date_to }}
            onChange={setRange}
            monthlyTotals={monthlyTotalsQ.data ?? []}
          />
          <select
            value={accountId ?? ''}
            onChange={(e) => setAccountId(e.target.value || undefined)}
            className="text-[13px] px-3 py-2 rounded-lg border border-border bg-input text-text"
          >
            <option value="">All Accounts</option>
            {(accountsQ.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.bank_name} {a.account_number_masked}
              </option>
            ))}
          </select>
          <button
            onClick={() => setRecategorizeOpen(true)}
            title="Re-run categorization rules over the selected range"
            className="flex items-center gap-1.5 text-[13px] px-3 py-2 rounded-lg border border-border bg-input text-text cursor-pointer"
          >
            <RefreshCw size={14} />
            Recategorize
          </button>
          <button
            onClick={openDialog}
            disabled={hasPendingBatch}
            className="text-[13px] font-semibold px-4 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            + Upload Statement
          </button>
        </div>
      </div>

      {recategorizeOpen && (
        <RecategorizeModal
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

      {/* Charts row 1 */}
      <div className="grid grid-cols-[1.3fr_1fr] gap-3.5 mb-3.5">
        <CashFlowChart data={s.cash_flow} />
        <CategoryDonut data={s.category_breakdown} categories={categoriesQ.data} rangeLabel={rangeLabel} />
      </div>

      {/* Charts row 2 */}
      <div className={`grid gap-3.5 mb-5 ${showVelocity ? 'grid-cols-[1.3fr_1fr]' : 'grid-cols-1'}`}>
        {showVelocity && (
          <VelocityChart
            data={s.spend_velocity}
            monthLabel={fmtMonthYearLabel(s.date_from)}
            prevMonthLabel={fmtMonthYearLabel(shiftMonth(s.date_from, -1))}
          />
        )}
        <div className="bg-card border border-border rounded-xl p-5">
          <div className="text-[13px] font-semibold mb-3">Top Merchants &amp; PayNow Contacts</div>
          <div className="text-[11px] text-muted-2 mb-1.5 uppercase tracking-wide">Merchants</div>
          {s.top_merchants.length === 0 && <div className="text-xs text-muted-2 py-1">No spending yet</div>}
          {s.top_merchants.map((m) => (
            <div key={m.name} className="flex justify-between text-[13px] py-1.5 border-b border-[#24252e]">
              <span>{m.name}</span>
              <span className="font-mono text-[#c6c6cf]">{fmtPlain(m.amount)}</span>
            </div>
          ))}
          <div className="text-[11px] text-muted-2 mt-3.5 mb-1.5 uppercase tracking-wide">PayNow Contacts</div>
          {s.top_paynow_contacts.length === 0 && <div className="text-xs text-muted-2 py-1">No PayNow transfers yet</div>}
          {s.top_paynow_contacts.map((p) => (
            <div key={p.name} className="flex justify-between text-[13px] py-1.5 border-b border-[#24252e]">
              <span>{p.name}</span>
              <span className="font-mono text-[#c6c6cf]">{fmtPlain(p.amount)}</span>
            </div>
          ))}
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
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-[13px] px-2.5 py-1.5 rounded-lg border border-border bg-input text-text"
            >
              <option value="">All Categories</option>
              {(categoriesQ.data ?? []).map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer whitespace-nowrap">
              <input
                type="checkbox"
                checked={excludedVisible}
                onChange={(e) => setExcludedVisible(e.target.checked)}
              />
              Show excluded
            </label>
          </div>
        </div>
        <div className="grid grid-cols-[80px_1fr_140px_130px_110px_30px_30px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-[#24252e]">
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
          const cc = categoryColor(categoriesQ.data, tx.category)
          return (
            <div key={tx.id}>
              <div
                className="grid grid-cols-[80px_1fr_140px_130px_110px_30px_30px] items-center px-5 py-3 text-[13px] border-b border-[#24252e] group"
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
                  <span className="text-[11px] px-2 py-0.5 rounded-md" style={{ background: cc.bg, color: cc.fg }}>
                    {tx.category}
                  </span>
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
                    className="border-none bg-transparent cursor-pointer text-muted-2 hover:text-text opacity-0 group-hover:opacity-100"
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
