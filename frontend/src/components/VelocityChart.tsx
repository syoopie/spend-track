import { useRef, useState } from 'react'
import type { MouseEvent as ReactMouseEvent } from 'react'
import type { VelocityPoint } from '../api/types'
import { fmtCompact, fmtDate, fmtPlain } from '../lib/format'

const LEFT_PAD = 42
const RIGHT_PAD = 6
const TOP_PAD = 8
const BOTTOM_PAD = 18
const PLOT_W = 460
const PLOT_H = 118

export function VelocityChart({
  data,
  periodLabel,
  prevPeriodLabel,
  bare = false,
}: {
  data: VelocityPoint[]
  periodLabel: string
  prevPeriodLabel: string
  bare?: boolean
}) {
  const width = LEFT_PAD + PLOT_W + RIGHT_PAD
  const height = TOP_PAD + PLOT_H + BOTTOM_PAD
  const max = Math.max(1, ...data.flatMap((p) => [p.current_period_cumulative, p.previous_period_cumulative]))
  const n = data.length
  const scaleX = (i: number) => LEFT_PAD + (n > 1 ? (i / (n - 1)) * PLOT_W : 0)
  const scaleY = (v: number) => TOP_PAD + PLOT_H - (v / max) * PLOT_H

  const currentPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.current_period_cumulative)}`).join(' ')
  const prevPoints = data.map((p, i) => `${scaleX(i)},${scaleY(p.previous_period_cumulative)}`).join(' ')
  const areaPath =
    n > 0
      ? `M ${scaleX(0)},${TOP_PAD + PLOT_H} L ${currentPoints} L ${scaleX(n - 1)},${TOP_PAD + PLOT_H} Z`
      : ''

  const gridFracs = [0, 0.33, 0.66, 1]

  const tickIdxs = n > 1 ? Array.from(new Set([0, Math.floor((n - 1) / 3), Math.floor((2 * (n - 1)) / 3), n - 1])) : []

  const finalCurrent = data.length ? data[data.length - 1].current_period_cumulative : 0
  const finalPrev = data.length ? data[data.length - 1].previous_period_cumulative : 0
  const delta = finalCurrent - finalPrev
  const deltaPct = finalPrev > 0 ? (delta / finalPrev) * 100 : null
  const spendingMore = delta > 0

  const svgRef = useRef<SVGSVGElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  function handleMouseMove(e: ReactMouseEvent<SVGSVGElement>) {
    if (!svgRef.current || n === 0) return
    const rect = svgRef.current.getBoundingClientRect()
    const xInViewBox = ((e.clientX - rect.left) / rect.width) * width
    const frac = n > 1 ? (xInViewBox - LEFT_PAD) / PLOT_W : 0
    setHoverIndex(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))))
  }

  const hovered = hoverIndex != null ? data[hoverIndex] : null
  const tooltipLeftPct = hoverIndex != null ? (scaleX(hoverIndex) / width) * 100 : 0

  const content = (
    <>
      <div className="text-[13px] font-semibold mb-3.5">Spend Velocity — Cumulative Pace</div>
      <div className="relative">
        <svg
          ref={svgRef}
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
          className="cursor-crosshair"
        >
          {gridFracs.map((f) => {
            const y = TOP_PAD + PLOT_H - f * PLOT_H
            return (
              <g key={f}>
                <line x1={LEFT_PAD} y1={y} x2={LEFT_PAD + PLOT_W} y2={y} stroke="var(--color-divider)" strokeWidth="1" />
                <text x={LEFT_PAD - 6} y={y + 3} textAnchor="end" fontSize="9" fill="var(--color-muted-2)">
                  {fmtCompact(f * max)}
                </text>
              </g>
            )
          })}
          {tickIdxs.map((i) => (
            <text key={i} x={scaleX(i)} y={TOP_PAD + PLOT_H + 13} textAnchor="middle" fontSize="9" fill="var(--color-muted-2)">
              {fmtDate(data[i].date)}
            </text>
          ))}
          {areaPath && <path d={areaPath} fill="var(--color-accent)" fillOpacity="0.1" stroke="none" />}
          <polyline points={prevPoints} fill="none" stroke="var(--color-dim)" strokeWidth="2" />
          <polyline points={currentPoints} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" />
          {n > 0 && (
            <circle cx={scaleX(n - 1)} cy={scaleY(finalCurrent)} r="3" fill="var(--color-accent)" />
          )}
          {hovered && (
            <g>
              <line
                x1={scaleX(hoverIndex!)}
                y1={TOP_PAD}
                x2={scaleX(hoverIndex!)}
                y2={TOP_PAD + PLOT_H}
                stroke="var(--color-muted-2)"
                strokeWidth="1"
                strokeDasharray="3 3"
              />
              <circle cx={scaleX(hoverIndex!)} cy={scaleY(hovered.current_period_cumulative)} r="3.5" fill="var(--color-accent)" stroke="var(--color-card)" strokeWidth="1.5" />
              <circle cx={scaleX(hoverIndex!)} cy={scaleY(hovered.previous_period_cumulative)} r="3.5" fill="var(--color-dim)" stroke="var(--color-card)" strokeWidth="1.5" />
            </g>
          )}
        </svg>
        {hovered && (
          <div
            className="absolute top-0 -translate-y-full pointer-events-none bg-card border border-border rounded-lg shadow-xl px-2.5 py-2 text-[11px] whitespace-nowrap z-10"
            style={{ left: `clamp(0px, ${tooltipLeftPct}%, calc(100% - 130px))` }}
          >
            <div className="font-semibold text-text mb-1">{fmtDate(hovered.date)}</div>
            <div className="flex items-center gap-1.5 text-accent">
              <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
              {periodLabel}: <span className="font-mono text-text">{fmtPlain(hovered.current_period_cumulative)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-dim">
              <span className="w-1.5 h-1.5 rounded-full bg-dim shrink-0" />
              {prevPeriodLabel}: <span className="font-mono text-text">{fmtPlain(hovered.previous_period_cumulative)}</span>
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between gap-3 flex-wrap mt-1.5">
        <div className="flex gap-4 text-[11px] text-muted">
          <span>
            <span className="text-accent">━</span> {periodLabel} (current)
          </span>
          <span>
            <span className="text-dim">━</span> {prevPeriodLabel}
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
    </>
  )

  if (bare) return content
  return <div className="bg-card border border-border rounded-xl p-5">{content}</div>
}
