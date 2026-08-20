import type { CashFlowMonth } from '../api/types'
import { fmtMonthLabel } from '../lib/format'

export function CashFlowChart({ data }: { data: CashFlowMonth[] }) {
  const max = Math.max(1, ...data.flatMap((d) => [d.inflow, d.outflow]))
  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="text-[13px] font-semibold mb-4">Cash Flow — Inflow vs Outflow</div>
      <div className="flex items-end gap-5.5 h-[150px] px-1.5">
        {data.map((m) => (
          <div key={m.month} className="flex flex-col items-center gap-1.5 flex-1">
            <div className="flex items-end gap-1 h-[120px]">
              <div
                className="w-3.5 rounded-t-[3px] bg-success"
                style={{ height: `${Math.max(1, (m.inflow / max) * 120)}px` }}
              />
              <div
                className="w-3.5 rounded-t-[3px] bg-[#3a3b48]"
                style={{ height: `${Math.max(1, (m.outflow / max) * 120)}px` }}
              />
            </div>
            <div className="text-[11px] text-muted-2">{fmtMonthLabel(m.month)}</div>
          </div>
        ))}
      </div>
      <div className="flex gap-4 text-[11px] text-muted mt-1.5">
        <span>
          <span className="text-success">■</span> Inflow
        </span>
        <span>
          <span className="text-[#3a3b48]">■</span> Outflow
        </span>
      </div>
    </div>
  )
}
