import type { VelocityPoint } from '../api/types'

export function VelocityChart({
  data,
  monthLabel,
  prevMonthLabel,
}: {
  data: VelocityPoint[]
  monthLabel: string
  prevMonthLabel: string
}) {
  const width = 480
  const height = 150
  const max = Math.max(1, ...data.flatMap((p) => [p.current_month_cumulative, p.previous_month_cumulative]))
  const scaleX = (i: number) => (data.length > 1 ? (i / (data.length - 1)) * width : 0)
  const scaleY = (v: number) => height - 1 - (v / max) * (height - 12)

  const currentPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.current_month_cumulative)}`).join(' ')
  const prevPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.previous_month_cumulative)}`).join(' ')

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="text-[13px] font-semibold mb-3.5">Spend Velocity — Cumulative Pace</div>
      <svg width="100%" height="150" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <line x1="0" y1={height - 1} x2={width} y2={height - 1} stroke="#2c2d38" strokeWidth="1" />
        <polyline points={prevPoints} fill="none" stroke="#3a3b48" strokeWidth="2" />
        <polyline points={currentPoints} fill="none" stroke="#e35fd0" strokeWidth="2.5" />
      </svg>
      <div className="flex gap-4 text-[11px] text-muted mt-1.5">
        <span>
          <span className="text-accent">━</span> {monthLabel} (current)
        </span>
        <span>
          <span className="text-[#3a3b48]">━</span> {prevMonthLabel}
        </span>
      </div>
    </div>
  )
}
