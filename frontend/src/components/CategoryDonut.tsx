import type { Category, CategoryBreakdownSlice } from '../api/types'
import { categoryDotColor } from '../lib/categoryColor'
import { fmtCompact } from '../lib/format'

export function CategoryDonut({
  data,
  categories,
  monthLabel,
}: {
  data: CategoryBreakdownSlice[]
  categories: Category[] | undefined
  monthLabel: string
}) {
  let cumulative = 0
  const stops = data.map((s) => {
    const from = cumulative
    cumulative += s.pct
    return `${categoryDotColor(categories, s.category)} ${from}% ${cumulative}%`
  })
  const gradient = stops.length ? `conic-gradient(${stops.join(', ')})` : '#3a3b48'
  const total = data.reduce((sum, s) => sum + s.amount, 0)

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="text-[13px] font-semibold mb-3.5">Category Breakdown — {monthLabel}</div>
      <div className="flex items-center gap-4.5">
        <div className="w-[110px] h-[110px] rounded-full relative shrink-0" style={{ background: gradient }}>
          <div className="absolute inset-5 bg-card rounded-full flex items-center justify-center text-xs font-bold font-mono">
            {fmtCompact(total)}
          </div>
        </div>
        <div className="flex flex-col gap-1.5 text-xs">
          {data.length === 0 && <div className="text-muted-2">No spending yet</div>}
          {data.map((s) => (
            <div key={s.category} className="flex items-center gap-1.5 text-[#c6c6cf]">
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ background: categoryDotColor(categories, s.category) }}
              />
              {s.category} <span className="text-muted-2">{s.pct}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
