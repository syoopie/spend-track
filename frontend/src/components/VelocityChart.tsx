import type { VelocityPoint } from '../api/types'
import { fmtCompact, fmtPlain } from '../lib/format'

const LEFT_PAD = 42
const RIGHT_PAD = 6
const TOP_PAD = 8
const BOTTOM_PAD = 18
const PLOT_W = 460
const PLOT_H = 118

export function VelocityChart({
  data,
  monthLabel,
  prevMonthLabel,
}: {
  data: VelocityPoint[]
  monthLabel: string
  prevMonthLabel: string
}) {
  const width = LEFT_PAD + PLOT_W + RIGHT_PAD
  const height = TOP_PAD + PLOT_H + BOTTOM_PAD
  const max = Math.max(1, ...data.flatMap((p) => [p.current_month_cumulative, p.previous_month_cumulative]))
  const n = data.length
  const scaleX = (i: number) => LEFT_PAD + (n > 1 ? (i / (n - 1)) * PLOT_W : 0)
  const scaleY = (v: number) => TOP_PAD + PLOT_H - (v / max) * PLOT_H

  const currentPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.current_month_cumulative)}`).join(' ')
  const prevPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.previous_month_cumulative)}`).join(' ')
  const areaPath =
    n > 0
      ? `M ${scaleX(0)},${TOP_PAD + PLOT_H} L ${currentPoints} L ${scaleX(n - 1)},${TOP_PAD + PLOT_H} Z`
      : ''

  const gridFracs = [0, 0.33, 0.66, 1]

  const tickIdxs = n > 1 ? Array.from(new Set([0, Math.floor((n - 1) / 3), Math.floor((2 * (n - 1)) / 3), n - 1])) : []

  const finalCurrent = data.length ? data[data.length - 1].current_month_cumulative : 0
  const finalPrev = data.length ? data[data.length - 1].previous_month_cumulative : 0
  const delta = finalCurrent - finalPrev
  const deltaPct = finalPrev > 0 ? (delta / finalPrev) * 100 : null
  const spendingMore = delta > 0

  return (
    <div className="bg-card border border-border rounded-xl p-5">
      <div className="text-[13px] font-semibold mb-3.5">Spend Velocity — Cumulative Pace</div>
      <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {gridFracs.map((f) => {
          const y = TOP_PAD + PLOT_H - f * PLOT_H
          return (
            <g key={f}>
              <line x1={LEFT_PAD} y1={y} x2={LEFT_PAD + PLOT_W} y2={y} stroke="#24252e" strokeWidth="1" />
              <text x={LEFT_PAD - 6} y={y + 3} textAnchor="end" fontSize="9" fill="#6b6c78">
                {fmtCompact(f * max)}
              </text>
            </g>
          )
        })}
        {tickIdxs.map((i) => (
          <text key={i} x={scaleX(i)} y={TOP_PAD + PLOT_H + 13} textAnchor="middle" fontSize="9" fill="#6b6c78">
            {data[i].day}
          </text>
        ))}
        {areaPath && <path d={areaPath} fill="var(--color-accent)" fillOpacity="0.1" stroke="none" />}
        <polyline points={prevPoints} fill="none" stroke="#3a3b48" strokeWidth="2" />
        <polyline points={currentPoints} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" />
        {n > 0 && (
          <circle cx={scaleX(n - 1)} cy={scaleY(finalCurrent)} r="3" fill="var(--color-accent)" />
        )}
      </svg>
      <div className="flex items-center justify-between gap-3 flex-wrap mt-1.5">
        <div className="flex gap-4 text-[11px] text-muted">
          <span>
            <span className="text-accent">━</span> {monthLabel} (current)
          </span>
          <span>
            <span className="text-[#3a3b48]">━</span> {prevMonthLabel}
          </span>
        </div>
        <div className="text-[11px] font-mono">
          <span className="text-muted-2">{fmtPlain(finalCurrent)}</span>
          <span className="text-muted-2"> vs {fmtPlain(finalPrev)} </span>
          {deltaPct !== null && (
            <span className={spendingMore ? 'text-danger-text' : 'text-success'}>
              ({spendingMore ? '+' : ''}
              {deltaPct.toFixed(0)}%)
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
