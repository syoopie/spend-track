import { useState } from 'react'
import type { Category, CategoryBreakdownSlice } from '../api/types'
import { Card } from './Card'
import { categoryDotColor, categoryIcon } from '../lib/categoryColor'
import { fmtCompact, fmtPlain } from '../lib/format'

// Kept a few units short of the viewBox's edge (60 from center) so the
// hover-expanded stroke width (24) doesn't get clipped by the SVG's default
// overflow: outer edge on hover = R + 24/2 = 58, inside the 60 boundary.
const R = 46
const CIRCUMFERENCE = 2 * Math.PI * R

// Beyond this many rows the legend becomes an unreadable wall of 12px text
// (DASH-5 in UI Review.dc.html) - collapse everything past it into one
// non-interactive "Other (n) · $amount" row. The ring itself still draws
// every real segment; only the text legend simplifies.
const LEGEND_HEAD = 6

export function CategoryDonut({
  data,
  categories,
  bare = false,
  onCategoryClick,
  selectedCategory,
}: {
  data: CategoryBreakdownSlice[]
  categories: Category[] | undefined
  bare?: boolean
  onCategoryClick?: (category: string) => void
  // The category the feed is currently filtered to (DASH-5) - kept at full
  // chroma/opacity even without an active hover, so "this is what's
  // filtering the feed" stays visible after the mouse moves away, not just
  // during the hover itself.
  selectedCategory?: string
}) {
  const [hovered, setHovered] = useState<string | null>(null)
  // Hover wins over the persisted selection while it's active - a user
  // scanning other slices shouldn't have the selected one visually pinned
  // in front of whichever slice their cursor is actually over.
  const active = hovered ?? selectedCategory ?? null

  let cumulativePct = 0
  const segments = data.map((s) => {
    const dash = (s.pct / 100) * CIRCUMFERENCE
    const offset = -(cumulativePct / 100) * CIRCUMFERENCE
    cumulativePct += s.pct
    return { ...s, dash, offset }
  })
  const total = data.reduce((sum, s) => sum + s.amount, 0)
  const activeSlice = data.find((s) => s.category === active)

  const head = data.slice(0, LEGEND_HEAD)
  const tail = data.slice(LEGEND_HEAD)
  const tailTotal = tail.reduce((sum, s) => sum + s.amount, 0)
  const tailPct = tail.reduce((sum, s) => sum + s.pct, 0)
  // Each legend row draws a bar proportional to the largest slice - the
  // same device the Top Merchants / Top Paynow tabs of this same card
  // already use. It's what gives the legend something to do with the width
  // a wide card hands it; stretched without one, every percentage just ends
  // up stranded a few hundred pixels from the name it belongs to.
  // Scaled against the largest row *including* the collapsed "Other" total,
  // which can exceed any single category - scaling to the top slice alone
  // clamped both to full width and made them read as equal.
  const barBasis = Math.max(data[0]?.pct ?? 0, tailPct)
  const barWidth = (pct: number) => (barBasis > 0 ? `${(pct / barBasis) * 100}%` : '0%')

  const content = (
    <>
      {!bare && <div className="text-md font-semibold mb-3.5">Category Breakdown</div>}
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
                    strokeWidth={active === seg.category ? 24 : 20}
                    strokeDasharray={`${seg.dash} ${CIRCUMFERENCE - seg.dash}`}
                    strokeDashoffset={seg.offset}
                    opacity={active && active !== seg.category ? 0.4 : 1}
                    onMouseEnter={() => setHovered(seg.category)}
                    onMouseLeave={() => setHovered(null)}
                    onClick={() => onCategoryClick?.(seg.category)}
                    className={
                      onCategoryClick
                        ? 'cursor-pointer transition-[stroke-width,opacity]'
                        : 'transition-[stroke-width,opacity]'
                    }
                  />
                ))}
              </g>
            </svg>
          )}
          <div className="absolute inset-5 bg-card rounded-full flex flex-col items-center justify-center text-center pointer-events-none">
            {activeSlice ? (
              <>
                <div className="text-[10px] font-bold font-mono">{fmtCompact(activeSlice.amount)}</div>
                <div className="text-[9px] text-muted-2">{activeSlice.pct}%</div>
              </>
            ) : (
              <div className="text-xs font-bold font-mono">{fmtCompact(total)}</div>
            )}
          </div>
        </div>
        {/* flex-1, so the legend spans whatever the card actually has
            rather than shrinking to its longest category name and leaving
            the rest of a wide card empty - each row's `ml-auto` then pushes
            the percentage and amount out to the card's right edge. */}
        <div className="flex flex-col gap-1.5 text-xs min-w-0 flex-1">
          {data.length === 0 && <div className="text-muted-2">No spending yet</div>}
          {head.map((s) => {
            const Icon = categoryIcon(categories, s.category)
            const isActive = active === s.category
            const color = categoryDotColor(categories, s.category)
            return (
              <div
                key={s.category}
                onMouseEnter={() => setHovered(s.category)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => onCategoryClick?.(s.category)}
                className={`relative flex items-center gap-1.5 rounded-md px-1 -mx-1 transition-colors ${
                  onCategoryClick ? 'cursor-pointer' : ''
                } ${isActive ? 'bg-input text-text' : 'text-text-2'} ${active && !isActive ? 'opacity-50' : ''}`}
              >
                {/* The row's own text is `relative` so it paints above this:
                    a positioned element outranks static siblings regardless
                    of DOM order, so without it the bar covers the label. */}
                <div
                  className="absolute inset-y-0 left-0 rounded pointer-events-none transition-[width,opacity]"
                  style={{ width: barWidth(s.pct), background: color, opacity: isActive ? 0.26 : 0.14 }}
                />
                <Icon size={12} color={color} className="shrink-0 relative" />
                <span className="truncate relative">{s.category}</span>
                {/* Amount now shows on every row, not just on hover (DASH-5) -
                    it used to require hovering each row in turn to see what
                    any of them actually cost. */}
                <span className="text-muted-2 shrink-0 ml-auto pl-1.5 relative">{s.pct}%</span>
                <span className="font-mono text-muted-2 shrink-0 relative">· {fmtPlain(s.amount)}</span>
              </div>
            )
          })}
          {tail.length > 0 && (
            <div className="relative flex items-center gap-1.5 rounded-md px-1 -mx-1 text-muted-2">
              <div
                className="absolute inset-y-0 left-0 rounded pointer-events-none bg-dim/40"
                style={{ width: barWidth(tailPct) }}
              />
              <span className="w-3 shrink-0 text-center relative">⋯</span>
              <span className="relative">Other ({tail.length})</span>
              <span className="ml-auto pl-1.5 relative">{Math.round(tailPct)}%</span>
              <span className="font-mono shrink-0 relative">· {fmtPlain(tailTotal)}</span>
            </div>
          )}
        </div>
      </div>
      {/* DASH-5: this was a real, useful filter control with zero indication
          it was clickable at all - no cursor hint at rest, no tooltip, no
          selected state left behind afterwards (the last of which is now
          handled by `selectedCategory` above). */}
      {onCategoryClick && data.length > 0 && (
        <div className="text-2xs text-muted-2 mt-2.5">Click a category to filter the feed below</div>
      )}
    </>
  )

  if (bare) return content
  return <Card>{content}</Card>
}
