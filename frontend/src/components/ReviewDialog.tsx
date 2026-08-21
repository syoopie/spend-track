import { Loader2, Sparkles } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useCategories } from '../api/hooks'
import type { AiJobStatus } from '../api/types'
import { categoryIcon } from '../lib/categoryColor'
import { fmtDate, fmtSigned } from '../lib/format'
import { CategoryBadge } from './CategoryBadge'
import { Checkbox } from './Checkbox'
import { Modal } from './Modal'
import { Select } from './Select'

const AMBER_BG = 'oklch(20% 0.02 70)'
const AMBER_BADGE_BG = 'oklch(30% 0.07 70)'
const AMBER_BADGE_FG = 'oklch(82% 0.13 70)'
const AI_BG = 'oklch(22% 0.045 285)'
const AI_BADGE_BG = 'oklch(30% 0.09 285)'
const AI_BADGE_FG = 'oklch(82% 0.1 285)'

// The hidden fallback category a row lands in when nothing (rule, contact,
// or AI) resolves it - what "reject this AI suggestion" reverts a row back
// to. Not offered in the category <Select> below (it's filtered to the
// visible category list, same as everywhere else in the app), so rejecting
// is its own explicit action rather than something reachable by picking
// from the dropdown.
function fallbackCategory(amount: number): string {
  return amount > 0 ? 'Other Income' : 'Others'
}

// Shared shape both the staging batch's rows and the recategorize batch's
// rows get mapped into, so the row list/popover only need to be written
// once - see StagingReviewDialog.tsx and RecategorizeReviewDialog.tsx.
export interface ReviewRow {
  key: number
  transaction_date: string
  raw_description: string
  matched_label: string | null
  amount: number
  category: string
  subcategory: string | null
  is_excluded: boolean
  exclusion_reason: string | null
  needs_review: boolean
  is_paynow: boolean
  ai_suggested: boolean
  ai_category: string | null
  ai_label: string | null
  ai_rule_pattern: string | null
}

// Whether the row is *currently* showing the AI's proposal - derived by
// comparing against the permanently-recorded ai_category, rather than
// tracked as its own mutable flag, so it can never drift out of sync with
// what's actually applied. Drives whether the popover offers "Reject" (it's
// currently applied - offer to back out) or "Restore" (it isn't - offer to
// bring it back), and the row's AI tint.
function aiIsCurrent(row: ReviewRow): boolean {
  return row.ai_category != null && row.category === row.ai_category
}

export interface ApplyRowBody {
  category: string
  save_as_rule: boolean
  rule_pattern?: string
  save_as_contact: boolean
  contact_name?: string
  contact_identifier?: string
  // True only for the explicit "Reject Suggestion" action - tells the
  // backend to also clear matched_label (the AI's display label) back to
  // null, not just the category. A plain Apply never sets this, even when
  // the chosen category happens to equal the fallback.
  reject_ai?: boolean
  // True only for the explicit "Restore Suggestion" action - tells the
  // backend to re-apply the row's recorded ai_category/ai_label, ignoring
  // `category` above.
  restore_ai?: boolean
}

export interface ReviewStatCard {
  label: string
  value: number
  tone?: 'default' | 'muted' | 'amber' | 'ai'
}

function StatCardView({ card }: { card: ReviewStatCard }) {
  if (card.tone === 'amber') {
    return (
      <div className="rounded-[10px] px-4.5 py-3" style={{ background: 'oklch(24% 0.05 70)', border: '1px solid oklch(40% 0.08 70)' }}>
        <div className="text-[11px]" style={{ color: 'oklch(80% 0.12 70)' }}>{card.label}</div>
        <div className="text-xl font-bold font-mono" style={{ color: 'oklch(85% 0.12 70)' }}>{card.value}</div>
      </div>
    )
  }
  if (card.tone === 'ai') {
    return (
      <div className="rounded-[10px] px-4.5 py-3" style={{ background: AI_BADGE_BG, border: '1px solid oklch(45% 0.1 285)' }}>
        <div className="text-[11px] flex items-center gap-1" style={{ color: AI_BADGE_FG }}>
          <Sparkles size={10} className="shrink-0" /> {card.label}
        </div>
        <div className="text-xl font-bold font-mono" style={{ color: AI_BADGE_FG }}>{card.value}</div>
      </div>
    )
  }
  return (
    <div className="bg-input border border-border rounded-[10px] px-4.5 py-3">
      <div className="text-[11px] text-muted-2">{card.label}</div>
      <div className={`text-xl font-bold font-mono ${card.tone === 'muted' ? 'text-muted-2' : ''}`}>{card.value}</div>
    </div>
  )
}

function ReviewRowPopover({
  row,
  onApply,
  applyPending,
}: {
  row: ReviewRow
  onApply: (body: ApplyRowBody) => Promise<void>
  applyPending: boolean
}) {
  const categoriesQ = useCategories()
  const [category, setCategory] = useState(row.category)
  const [saveAsRule, setSaveAsRule] = useState(row.ai_suggested && aiIsCurrent(row))
  const [rulePattern, setRulePattern] = useState(row.ai_rule_pattern ?? '')
  const [saveAsContact, setSaveAsContact] = useState(false)

  const direction = row.amount > 0 ? 'inflow' : 'outflow'
  const categoryOptions = (categoriesQ.data ?? []).filter((c) => c.direction === direction)
  const current = aiIsCurrent(row)

  return (
    <div
      className="px-5 py-4 flex flex-col gap-3 border-b border-border"
      style={{ background: row.ai_suggested && current ? AI_BG : row.needs_review ? AMBER_BG : 'var(--color-input)' }}
    >
      {row.ai_suggested && current && (
        <div className="text-[11px] flex items-center gap-1.5" style={{ color: AI_BADGE_FG }}>
          <Sparkles size={11} className="shrink-0" />
          AI suggested this category and label — review before applying, or reject it below.
        </div>
      )}
      {row.ai_suggested && !current && (
        <div className="text-[11px] flex items-center gap-1.5" style={{ color: 'var(--color-muted-2)' }}>
          <Sparkles size={11} className="shrink-0" />
          AI suggested "{row.ai_category}" for this transaction — you're not using that suggestion right now.
          Restore it below if you'd like.
        </div>
      )}
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="text-[11px] text-muted mb-1">Assign category · {direction === 'inflow' ? 'Inflow' : 'Outflow'}</div>
          <Select uiSize="sm" value={category} onChange={(e) => setCategory(e.target.value)} className="w-full">
            {categoryOptions.map((c) => {
              const Icon = categoryIcon(categoriesQ.data, c.name)
              return (
                <option key={c.id} value={c.name}>
                  <span className="inline-flex items-center gap-1.5">
                    <Icon size={12} className="shrink-0" />
                    {c.name}
                  </span>
                </option>
              )
            })}
          </Select>
        </div>
        {/* A PayNow line's "match text" is a free-text payee name, not a
            reusable merchant keyword, so it's never rule-eligible - the only
            way to resolve it going forward is a contact mapping. Every other
            row is the reverse: no identifiable payee to attach a contact
            to, so only "Save as rule" applies. */}
        {!row.is_paynow && (
          <label className="flex items-center gap-1.5 text-[12px] text-text pb-2 cursor-pointer">
            <Checkbox checked={saveAsRule} onChange={setSaveAsRule} />
            Save as rule
          </label>
        )}
        {row.is_paynow && (
          <label className="flex items-center gap-1.5 text-[12px] text-text pb-2 cursor-pointer">
            <Checkbox checked={saveAsContact} onChange={setSaveAsContact} />
            Save as contact mapping
          </label>
        )}
        {row.ai_suggested && current && (
          <button
            onClick={() =>
              onApply({ category: fallbackCategory(row.amount), save_as_rule: false, save_as_contact: false, reject_ai: true })
            }
            disabled={applyPending}
            title="Discard the AI's suggestion and leave this transaction unresolved again"
            className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border border-border bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-60"
          >
            Reject Suggestion
          </button>
        )}
        {row.ai_suggested && !current && (
          <button
            onClick={() =>
              onApply({ category: row.ai_category!, save_as_rule: false, save_as_contact: false, restore_ai: true })
            }
            disabled={applyPending}
            title="Bring back the AI's suggestion for this transaction"
            className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border border-border bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-60"
          >
            Restore Suggestion
          </button>
        )}
        <button
          onClick={() =>
            onApply({
              category,
              save_as_rule: saveAsRule,
              rule_pattern: saveAsRule ? rulePattern || undefined : undefined,
              save_as_contact: saveAsContact,
            })
          }
          disabled={applyPending}
          className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Apply
        </button>
      </div>
      {saveAsRule && (
        <div>
          <div className="text-[11px] text-muted mb-1">Rule pattern (substring match, blank uses the cleaned name)</div>
          <input
            value={rulePattern}
            onChange={(e) => setRulePattern(e.target.value)}
            placeholder={row.raw_description}
            className="w-full box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-[12px] font-mono"
          />
        </div>
      )}
    </div>
  )
}

export function ReviewDialog({
  title,
  subtitle,
  onClose,
  statCards,
  aiStatus,
  aiWarning,
  aiModel,
  rows,
  onApplyRow,
  applyPending,
  footer,
  emptyMessage = 'Nothing to show.',
}: {
  title: string
  subtitle: string
  onClose: () => void
  statCards: ReviewStatCard[]
  aiStatus: AiJobStatus
  aiWarning: string | null
  aiModel: string | null
  rows: ReviewRow[]
  onApplyRow: (row: ReviewRow, body: ApplyRowBody) => Promise<void>
  applyPending: boolean
  footer: ReactNode
  emptyMessage?: string
}) {
  const [openKey, setOpenKey] = useState<number | null>(null)
  const categoriesQ = useCategories()

  return (
    <Modal onClose={onClose} width={860}>
      <div className="flex items-start justify-between mb-0.5">
        <div>
          <div className="text-lg font-bold">{title}</div>
          <div className="text-[13px] text-muted mt-0.5 mb-4">{subtitle}</div>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-text text-lg leading-none cursor-pointer border-none bg-transparent"
        >
          ×
        </button>
      </div>

      {/* Purely informational - never disables the × above, so the dialog is
          always dismissible while this runs. Individual callers may disable
          their own footer actions during this state (e.g. staging disables
          Commit) - see each dialog's own footer. The background AI job keeps
          running whether this dialog is open or closed; closing just stops
          watching it. */}
      {aiStatus === 'running' && (
        <div
          className="rounded-[10px] px-4 py-2.5 mb-4 flex items-center gap-2 text-[12px]"
          style={{ background: AI_BG, color: AI_BADGE_FG }}
        >
          <Loader2 size={14} className="animate-spin shrink-0" />
          AI is categorizing leftover transactions with {aiModel}… you can keep working, or close this and check
          back later.
        </div>
      )}
      {aiStatus === 'failed' && aiWarning && (
        <div
          className="rounded-[10px] px-4 py-2.5 mb-4 text-[12px]"
          style={{ background: 'oklch(24% 0.05 70)', color: 'oklch(85% 0.1 70)' }}
        >
          {aiWarning}
        </div>
      )}

      {statCards.length > 0 && (
        <div className="flex gap-3 mb-5 flex-wrap">
          {statCards.map((c) => (
            <StatCardView key={c.label} card={c} />
          ))}
        </div>
      )}

      <div className="bg-input border border-border rounded-xl overflow-y-auto mb-5 max-h-[45vh]">
        <div className="grid grid-cols-[80px_1fr_180px_110px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-border/70 sticky top-0 bg-input">
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div className="text-right">Amount</div>
        </div>
        {rows.length === 0 && <div className="p-5 text-muted text-sm">{emptyMessage}</div>}
        {/* Every row is reviewable/clickable regardless of AI or needs_review
            state - adding a rule or contact mapping shouldn't be gated on
            whether AI touched the row. AI-suggested rows are stably sorted
            to the top so they're easy to find and review as a group. */}
        {[...rows]
          .sort((a, b) => Number(b.ai_suggested) - Number(a.ai_suggested))
          .map((row) => {
          const isOpen = openKey === row.key
          const current = aiIsCurrent(row)
          const colorOverride = row.needs_review
            ? { bg: AMBER_BADGE_BG, fg: AMBER_BADGE_FG }
            : row.ai_suggested && current
              ? { bg: AI_BADGE_BG, fg: AI_BADGE_FG }
              : undefined
          const rowBg = row.needs_review ? AMBER_BG : row.ai_suggested && current ? AI_BG : undefined
          return (
            <div key={row.key}>
              <div
                onClick={() => setOpenKey(isOpen ? null : row.key)}
                className="grid grid-cols-[80px_1fr_180px_110px] items-center px-5 py-2.5 text-[13px] border-b border-border/70 cursor-pointer"
                style={{ background: rowBg ?? (isOpen ? 'var(--color-input)' : undefined) }}
              >
                <div className="text-muted font-mono text-xs">{fmtDate(row.transaction_date)}</div>
                <div className="min-w-0 pr-2 flex items-center gap-1.5">
                  {row.ai_suggested && (
                    <Sparkles size={11} className="shrink-0" style={{ color: current ? AI_BADGE_FG : 'var(--color-muted-2)' }} />
                  )}
                  <div className="min-w-0">
                    <div className="truncate">{row.matched_label ?? row.raw_description}</div>
                    {/* The clean label/AI suggestion is never the only thing shown - the
                        full raw bank description stays visible underneath it, not just
                        in a hover title, so it's never hidden behind an edited name. */}
                    {row.matched_label && (
                      <div className="truncate text-[10.5px] text-muted-2" title={row.raw_description}>
                        {row.raw_description}
                      </div>
                    )}
                  </div>
                </div>
                <div>
                  <CategoryBadge category={row.category} categories={categoriesQ.data} colorOverride={colorOverride} />
                </div>
                <div className={`text-right font-mono ${row.amount > 0 ? 'text-success' : 'text-text'}`}>
                  {fmtSigned(row.amount)}
                </div>
              </div>
              {isOpen && (
                <ReviewRowPopover
                  row={row}
                  applyPending={applyPending}
                  onApply={async (body) => {
                    try {
                      await onApplyRow(row, body)
                      setOpenKey(null)
                    } catch {
                      // leave the popover open on failure so the user can retry
                    }
                  }}
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-end gap-3">{footer}</div>
    </Modal>
  )
}
