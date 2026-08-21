import { useState } from 'react'
import type { Category, CategoryBreakdownSlice } from '../api/types'
import { categoryDotColor, categoryIcon } from '../lib/categoryColor'
import { fmtCompact, fmtPlain } from '../lib/format'

// Kept a few units short of the viewBox's edge (60 from center) so the
// hover-expanded stroke width (24) doesn't get clipped by the SVG's default
// overflow: outer edge on hover = R + 24/2 = 58, inside the 60 boundary.
const R = 46
const CIRCUMFERENCE = 2 * Math.PI * R

export function CategoryDonut({
  data,
  categories,
  bare = false,
  onCategoryClick,
}: {
  data: CategoryBreakdownSlice[]
  categories: Category[] | undefined
  bare?: boolean
  onCategoryClick?: (category: string) => void
}) {
  const [hovered, setHovered] = useState<string | null>(null)

  let cumulativePct = 0
  const segments = data.map((s) => {
    const dash = (s.pct / 100) * CIRCUMFERENCE
    const offset = -(cumulativePct / 100) * CIRCUMFERENCE
    cumulativePct += s.pct
    return { ...s, dash, offset }
  })
  const total = data.reduce((sum, s) => sum + s.amount, 0)
  const hoveredSlice = data.find((s) => s.category === hovered)

  const content = (
    <>
      <div className="text-[13px] font-semibold mb-3.5">Category Breakdown</div>
      <div className="flex items-center gap-4.5">
        <div className="w-[110px] h-[110px] relative shrink-0">
          {segments.length === 0 ? (
            <svg viewBox="0 0 120 120" className="w-full h-full">
              <circle cx="60" cy="60" r={R} fill="none" stroke="var(--color-dim)" strokeWidth="20" />
            </svg>
          ) : (
            <svg viewBox="0 0 120 120" className="w-full h-full">
              <g transform="rotate(-90 60 60)">
                {segments.map((seg) => (
                  <circle
                    key={seg.category}
                    cx="60"
                    cy="60"
                    r={R}
                    fill="none"
                    stroke={categoryDotColor(categories, seg.category)}
                    strokeWidth={hovered === seg.category ? 24 : 20}
                    strokeDasharray={`${seg.dash} ${CIRCUMFERENCE - seg.dash}`}
                    strokeDashoffset={seg.offset}
                    opacity={hovered && hovered !== seg.category ? 0.4 : 1}
                    onMouseEnter={() => setHovered(seg.category)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => onCategoryClick?.(seg.category)}
                    className={onCategoryClick ? 'cursor-pointer transition-all' : 'transition-all'}
                  />
                ))}
              </g>
            </svg>
          )}
          <div className="absolute inset-5 bg-card rounded-full flex flex-col items-center justify-center text-center pointer-events-none">
            {hoveredSlice ? (
              <>
                <div className="text-[10px] font-bold font-mono">{fmtCompact(hoveredSlice.amount)}</div>
                <div className="text-[9px] text-muted-2">{hoveredSlice.pct}%</div>
              </>
            ) : (
              <div className="text-xs font-bold font-mono">{fmtCompact(total)}</div>
            )}
          </div>
        </div>
        <div className="flex flex-col gap-1.5 text-xs">
          {data.length === 0 && <div className="text-muted-2">No spending yet</div>}
          {data.map((s) => {
            const Icon = categoryIcon(categories, s.category)
            const isHovered = hovered === s.category
            return (
              <div
                key={s.category}
                onMouseEnter={() => setHovered(s.category)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onCategoryClick?.(s.category)}
                className={`flex items-center gap-1.5 rounded-md px-1 -mx-1 transition-colors ${
                  onCategoryClick ? 'cursor-pointer' : ''
                } ${isHovered ? 'bg-input text-text' : 'text-text-2'} ${hovered && !isHovered ? 'opacity-50' : ''}`}
              >
                <Icon size={12} color={categoryDotColor(categories, s.category)} className="shrink-0" />
                {s.category} <span className="text-muted-2">{s.pct}%</span>
                {isHovered && <span className="font-mono text-muted-2">· {fmtPlain(s.amount)}</span>}
              </div>
            )
          })}
        </div>
      </div>
    </>
  )

  if (bare) return content
  return <div className="bg-card border border-border rounded-xl p-5">{content}</div>
}
