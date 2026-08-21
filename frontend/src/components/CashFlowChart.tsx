import type { CashFlowMonth, MonthlyTotal } from '../api/types'
import { fmtCompact, fmtMonthLabel } from '../lib/format'

const TREND_WINDOW = 6

export function CashFlowChart({
  data,
  trend,
  selectedMonth,
}: {
  data: CashFlowMonth[]
  trend?: MonthlyTotal[]
  selectedMonth?: string
}) {
  const useTrend = data.length <= 1 && selectedMonth && trend && trend.length > 1
  const chartData = useTrend ? trend.filter((m) => m.month <= selectedMonth).slice(-TREND_WINDOW) : data

  const max = Math.max(1, ...chartData.flatMap((d) => [d.inflow, d.outflow]))
  const title = useTrend ? `Cash Flow — Trend into ${fmtMonthLabel(selectedMonth)}` : 'Cash Flow — Inflow vs Outflow'

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="text-[13px] font-semibold mb-4">{title}</div>
      <div className="flex items-end gap-3.5 h-[150px] px-1.5">
        {chartData.map((m) => {
          const isSelected = !useTrend || m.month === selectedMonth
          return (
            <div key={m.month} className={`flex flex-col items-center gap-1.5 flex-1 ${isSelected ? '' : 'opacity-45'}`}>
              <div className="flex items-end gap-1 h-[120px]">
                <div className="flex flex-col items-center justify-end h-full">
                  {m.inflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.inflow)}</div>}
                  <div
                    className="w-3.5 rounded-t-[3px] bg-success"
                    style={{ height: `${Math.max(1, (m.inflow / max) * 120)}px` }}
                  />
                </div>
                <div className="flex flex-col items-center justify-end h-full">
                  {m.outflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.outflow)}</div>}
                  <div
                    className="w-3.5 rounded-t-[3px]"
                    style={{ height: `${Math.max(1, (m.outflow / max) * 120)}px`, background: isSelected ? 'var(--color-accent)' : '#3a3b48' }}
                  />
                </div>
              </div>
              <div className={`text-[11px] ${isSelected ? 'text-text font-semibold' : 'text-muted-2'}`}>
                {fmtMonthLabel(m.month)}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 text-[11px] text-muted mt-1.5">
        <span>
          <span className="text-success">■</span> Inflow
        </span>
        <span>
          <span className={useTrend ? 'text-accent' : 'text-[#3a3b48]'}>■</span> Outflow{useTrend ? ' (selected month)' : ''}
        </span>
        {useTrend && (
          <span>
            <span className="text-[#3a3b48]">■</span> Outflow (prior months)
          </span>
        )}
      </div>
    </div>
  )
}
