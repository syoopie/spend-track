import { useMemo, useState } from 'react'
import { useAccounts, useCategories, useDashboardSummary, useTransactions } from '../api/hooks'
import { categoryColor } from '../lib/categoryColor'
import { fmtDate, fmtMonthYearLabel, fmtPlain, fmtSigned } from '../lib/format'
import { CashFlowChart } from '../components/CashFlowChart'
import { CategoryDonut } from '../components/CategoryDonut'
import { VelocityChart } from '../components/VelocityChart'
import { RefundDrawer } from '../components/RefundDrawer'
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
  const { openDialog } = useUploadDialog()
  const [month, setMonth] = useState<string | undefined>(undefined)
  const [accountId, setAccountId] = useState<string | undefined>(undefined)
  const [excludedVisible, setExcludedVisible] = useState(true)
  const [refundTxId, setRefundTxId] = useState<number | null>(null)

  const accountsQ = useAccounts()
  const categoriesQ = useCategories()
  const summaryQ = useDashboardSummary({ month, account_id: accountId })
  const resolvedMonth = month ?? summaryQ.data?.month
  const txQ = useTransactions({ month: resolvedMonth, account_id: accountId, include_excluded: true })

  const prevCashFlow = summaryQ.data ? summaryQ.data.cash_flow[summaryQ.data.cash_flow.length - 2] : undefined
  const curCashFlow = summaryQ.data ? summaryQ.data.cash_flow[summaryQ.data.cash_flow.length - 1] : undefined
  const outflowChangePct =
    prevCashFlow && curCashFlow && prevCashFlow.outflow > 0
      ? Math.round(((curCashFlow.outflow - prevCashFlow.outflow) / prevCashFlow.outflow) * 100)
      : null

  const visibleTransactions = useMemo(
    () => (txQ.data ?? []).filter((t) => excludedVisible || !t.is_excluded),
    [txQ.data, excludedVisible],
  )
  const inflowCount = (txQ.data ?? []).filter((t) => t.amount > 0).length
  const distinctAccounts = new Set((txQ.data ?? []).map((t) => t.account_id)).size

  if (summaryQ.isLoading || !summaryQ.data || accountsQ.isLoading) {
    return <div className="p-9 text-muted">Loading dashboard…</div>
  }

  if ((accountsQ.data ?? []).length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center p-10">
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
            className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer"
          >
            + Upload Statement
          </button>
        </div>
      </div>
    )
  }

  const s = summaryQ.data
  const monthLabel = fmtMonthYearLabel(s.month)
  const prevMonthLabel = prevCashFlow ? fmtMonthYearLabel(prevCashFlow.month) : 'previous month'

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="flex items-start justify-between mb-5.5 gap-4 flex-wrap">
        <div>
          <div className="text-[22px] font-bold">Dashboard</div>
          <div className="text-[13px] text-muted mt-0.5">Post-mortem view of where the money went</div>
        </div>
        <div className="flex gap-2.5 items-center">
          <input
            type="month"
            value={resolvedMonth ?? ''}
            onChange={(e) => setMonth(e.target.value || undefined)}
            className="text-[13px] px-3 py-2 rounded-lg border border-border bg-input text-text"
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
            onClick={openDialog}
            className="text-[13px] font-semibold px-4 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer"
          >
            + Upload Statement
          </button>
        </div>
      </div>

      {/* Metric cards */}
      <div className="grid grid-cols-4 gap-3.5 mb-5">
        <MetricCard
          label="Net Expenditure"
          value={fmtPlain(s.metrics.net_expenditure)}
          hint={
            outflowChangePct === null
              ? undefined
              : `${outflowChangePct >= 0 ? '▲' : '▼'} ${Math.abs(outflowChangePct)}% vs ${prevMonthLabel}`
          }
        />
        <MetricCard
          label="Total Inflow"
          value={fmtPlain(s.metrics.total_inflow)}
          valueClassName="text-success"
          hint={`${inflowCount} inflow transaction${inflowCount === 1 ? '' : 's'}`}
        />
        <MetricCard
          label="Total Outflow"
          value={fmtPlain(s.metrics.total_outflow)}
          hint={`across ${distinctAccounts} account${distinctAccounts === 1 ? '' : 's'}`}
        />
        <div className="bg-card border border-border rounded-xl p-4.5">
          <div className="text-xs text-muted mb-2.5">PayNow vs Card Spend</div>
          <div className="flex h-2 rounded overflow-hidden mb-2">
            <div className="bg-[oklch(72%_0.14_20)]" style={{ width: `${s.metrics.paynow_pct}%` }} />
            <div className="bg-[oklch(72%_0.14_230)]" style={{ width: `${s.metrics.card_pct}%` }} />
          </div>
          <div className="flex flex-wrap justify-between gap-1 text-xs text-muted">
            <span className="whitespace-nowrap">
              <span className="text-[oklch(72%_0.14_20)] font-semibold">●</span> PayNow {s.metrics.paynow_pct}%
            </span>
            <span className="whitespace-nowrap">
              <span className="text-[oklch(72%_0.14_230)] font-semibold">●</span> Card {s.metrics.card_pct}%
            </span>
          </div>
        </div>
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-[1.3fr_1fr] gap-3.5 mb-3.5">
        <CashFlowChart data={s.cash_flow} />
        <CategoryDonut data={s.category_breakdown} categories={categoriesQ.data} monthLabel={monthLabel} />
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-[1.3fr_1fr] gap-3.5 mb-5">
        <VelocityChart data={s.spend_velocity} monthLabel={monthLabel} prevMonthLabel={prevMonthLabel} />
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
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="text-[13px] font-semibold">Transaction Feed</div>
          <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer">
            <input
              type="checkbox"
              checked={excludedVisible}
              onChange={(e) => setExcludedVisible(e.target.checked)}
            />
            Show excluded transactions
          </label>
        </div>
        <div className="grid grid-cols-[80px_1fr_140px_130px_110px_30px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-[#24252e]">
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div>Account</div>
          <div className="text-right">Amount</div>
          <div />
        </div>
        {txQ.isLoading && <div className="p-5 text-muted text-sm">Loading transactions…</div>}
        {!txQ.isLoading && visibleTransactions.length === 0 && (
          <div className="p-5 text-muted text-sm">No transactions for this month yet.</div>
        )}
        {visibleTransactions.map((tx) => {
          const cc = categoryColor(categoriesQ.data, tx.category)
          return (
            <div
              key={tx.id}
              className="grid grid-cols-[80px_1fr_140px_130px_110px_30px] items-center px-5 py-3 text-[13px] border-b border-[#24252e]"
              style={{ opacity: tx.is_excluded ? 0.5 : 1 }}
            >
              <div className="text-muted font-mono text-xs">{fmtDate(tx.transaction_date)}</div>
              <div className="truncate pr-2">
                {tx.raw_description}
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
              <div className={`text-right font-mono ${tx.amount > 0 ? 'text-success' : 'text-text'}`}>
                {fmtSigned(tx.amount)}
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
            </div>
          )
        })}
      </div>

      {refundTxId != null && <RefundDrawer transactionId={refundTxId} onClose={() => setRefundTxId(null)} />}
    </div>
  )
}
