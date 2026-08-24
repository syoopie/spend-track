import { Inbox, ListPlus, Loader2, RotateCcw, Sparkles, Undo2 } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { useCategories } from '../api/hooks'
import type { AiJobStatus, RuleRerunRowSnapshot } from '../api/types'
import { categoryIcon } from '../lib/categoryColor'
import { fmtDate, fmtSigned } from '../lib/format'
import { CategoryBadge } from './CategoryBadge'
import { Checkbox } from './Checkbox'
import { EmptyState } from './EmptyState'
import { Modal } from './Modal'
import { Select } from './Select'

const AMBER_BG = 'var(--color-warning-surface)'
const AMBER_BADGE_BG = 'var(--color-warning-badge-bg)'
const AMBER_BADGE_FG = 'var(--color-warning-text)'
const AI_BG = 'var(--color-ai-surface)'
const AI_BADGE_BG = 'var(--color-ai-badge-bg)'
const AI_BADGE_FG = 'var(--color-ai-text)'
const SUCCESS_BG = 'var(--color-success-surface)'
const SUCCESS_FG = 'var(--color-success-text)'

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
  // The rules/contact/PayNow engine's answer before any AI or manual edit -
  // what the single "Restore Default" button falls back to when there's no
  // ai_category to prefer instead.
  original_category: string
  original_label: string | null
  ai_suggested: boolean
  ai_category: string | null
  ai_label: string | null
  ai_rule_pattern: string | null
}

// Whether the row is *currently* showing the AI's proposal - derived by
// comparing against the permanently-recorded ai_category, rather than
// tracked as its own mutable flag, so it can never drift out of sync with
// what's actually applied. Drives the row's AI tint and banner wording.
function aiIsCurrent(row: ReviewRow): boolean {
  return row.ai_category != null && row.category === row.ai_category
}

// Same "would the backend send this row to the AI" test as
// routers/statements.py::_ai_candidates - a row that hasn't been resolved by
// a rule/contact/PayNow match and hasn't come back from the AI yet. Only
// meaningful while aiStatus === 'running': it's what gets pulled into the
// "AI is working on these" group at the top of the row list.
function isAiPending(row: ReviewRow): boolean {
  return !row.ai_suggested && row.matched_label == null && (row.category === 'Others' || row.category === 'Other Income')
}

function byDateDesc(a: ReviewRow, b: ReviewRow): number {
  return b.transaction_date.localeCompare(a.transaction_date)
}

export interface ApplyRowBody {
  category: string
  // Always sent alongside category on a plain edit (never omitted) - the
  // backend applies both together, so leaving this out would silently wipe
  // the label back to null the next time only the category changes.
  matched_label?: string | null
  save_as_contact: boolean
  contact_name?: string
  contact_identifier?: string
  // True only for the single "Restore Default" action - tells the backend
  // to ignore category/matched_label above and instead re-apply
  // ai_category/ai_label if an AI suggestion exists, else
  // original_category/original_label.
  restore_default?: boolean
}

export interface ReviewStatCard {
  label: string
  value: number
  tone?: 'default' | 'muted' | 'amber' | 'ai'
}

function StatCardView({ card }: { card: ReviewStatCard }) {
  if (card.tone === 'amber') {
    return (
      <div className="rounded-2lg px-4.5 py-3" style={{ background: 'var(--color-warning-surface)', border: '1px solid var(--color-warning-surface-border)' }}>
        <div className="text-2xs" style={{ color: 'var(--color-warning-text)' }}>{card.label}</div>
        <div className="text-xl font-bold font-mono" style={{ color: 'var(--color-warning-text)' }}>{card.value}</div>
      </div>
    )
  }
  if (card.tone === 'ai') {
    return (
      <div className="rounded-2lg px-4.5 py-3" style={{ background: AI_BADGE_BG, border: '1px solid var(--color-ai-surface-border)' }}>
        <div className="text-2xs flex items-center gap-1" style={{ color: AI_BADGE_FG }}>
          <Sparkles size={10} className="shrink-0" /> {card.label}
        </div>
        <div className="text-xl font-bold font-mono" style={{ color: AI_BADGE_FG }}>{card.value}</div>
      </div>
    )
  }
  return (
    <div className="bg-input border border-border rounded-2lg px-4.5 py-3">
      <div className="text-2xs text-muted-2">{card.label}</div>
      <div className={`text-xl font-bold font-mono ${card.tone === 'muted' ? 'text-muted-2' : ''}`}>{card.value}</div>
    </div>
  )
}

function ReviewRowPopover({
  row,
  onApply,
  applyPending,
  onCreateRule,
  createRulePending,
}: {
  row: ReviewRow
  onApply: (body: ApplyRowBody) => Promise<void>
  applyPending: boolean
  onCreateRule: (matchPattern: string, targetCategory: string, displayLabel: string | null) => Promise<void>
  createRulePending: boolean
}) {
  const categoriesQ = useCategories()
  const [category, setCategory] = useState(row.category)
  const [label, setLabel] = useState(row.matched_label ?? '')
  // Tracks the last value actually sent to the backend, so a blur that
  // didn't change anything (click into the field, click back out) doesn't
  // fire a redundant request - see applyLabel below. Not the same as
  // row.matched_label, which stays stale (the prop this component mounted
  // with) across edits made within this same open popover.
  const appliedLabelRef = useRef<string | null>(row.matched_label)
  const [rulePattern, setRulePattern] = useState(row.ai_rule_pattern ?? '')
  const [saveAsContact, setSaveAsContact] = useState(false)

  const direction = row.amount > 0 ? 'inflow' : 'outflow'
  const categoryOptions = (categoriesQ.data ?? []).filter((c) => c.direction === direction)
  const current = aiIsCurrent(row)
  // What the single "Restore Default" button below resets this row to -
  // the AI's suggestion when one exists, else the rules engine's original
  // answer. Mirrors engine/batch_review.py::apply_row_update's own
  // restore_default branch exactly, so the button's effect can be predicted
  // (and its disabled state computed) without waiting on a round trip.
  const defaultTarget = row.ai_category != null
    ? { category: row.ai_category, label: row.ai_label }
    : { category: row.original_category, label: row.original_label }
  const atDefault = category === defaultTarget.category && (label.trim() || null) === defaultTarget.label

  function applyLabel() {
    const next = label.trim() || null
    if (next === appliedLabelRef.current) return
    appliedLabelRef.current = next
    onApply({ category, matched_label: next, save_as_contact: saveAsContact })
  }

  function restoreDefault() {
    setCategory(defaultTarget.category)
    setLabel(defaultTarget.label ?? '')
    appliedLabelRef.current = defaultTarget.label
    onApply({ category, save_as_contact: false, restore_default: true })
  }

  return (
    <div
      className="px-5 py-4 flex flex-col gap-3 border-b border-border"
      style={{ background: row.ai_suggested && current ? AI_BG : row.needs_review ? AMBER_BG : 'var(--color-input)' }}
    >
      {/* Restore Default lives here, not squeezed into the category row below
          - that row's other occupant (the PayNow "save as contact" checkbox)
          only exists on some rows, which used to shift the button sideways
          depending on row type. Anchoring it to this always-present header
          row keeps it in the same spot for every row, and pairs it visually
          with the AI copy it's the direct undo/redo for. */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {row.ai_suggested && current && (
            <div className="text-2xs flex items-center gap-1.5" style={{ color: AI_BADGE_FG }}>
              <Sparkles size={11} className="shrink-0" />
              AI suggested this category and label — edit them below if you'd like.
            </div>
          )}
          {row.ai_suggested && !current && (
            <div className="text-2xs flex items-center gap-1.5" style={{ color: 'var(--color-muted-2)' }}>
              <Sparkles size={11} className="shrink-0" />
              AI suggested "{row.ai_category}" for this transaction — you're not using that suggestion right now.
            </div>
          )}
        </div>
        {/* Single button regardless of AI/manual-edit state - it always
            resets to the same predictable target (see defaultTarget above),
            so there's no separate "reject" vs "restore" decision for the
            user to make; disabled once the row already matches that target. */}
        <button
          onClick={restoreDefault}
          disabled={applyPending || atDefault}
          title={
            row.ai_category != null
              ? "Reset to the AI's suggested category and display name"
              : 'Reset to the original category and display name'
          }
          className="shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-border bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RotateCcw size={12} className="shrink-0" />
          Restore Default
        </button>
      </div>
      <div>
        <div className="text-2xs text-muted mb-1">Display name</div>
        {/* Applies on blur/Enter, not per keystroke - unlike category/the
            checkbox, which fire on their own discrete change events. */}
        <input
          value={label}
          disabled={applyPending}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={applyLabel}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }}
          placeholder={row.raw_description}
          className="w-full box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-md"
        />
      </div>
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="text-2xs text-muted mb-1">Assign category · {direction === 'inflow' ? 'Inflow' : 'Outflow'}</div>
          {/* Picking a category applies it immediately - no separate Apply
              button. Re-picking the row's current value is a no-op (nothing
              actually changed), so it doesn't fire a redundant request. */}
          <Select
            uiSize="sm"
            value={category}
            disabled={applyPending}
            onChange={(e) => {
              const next = e.target.value
              setCategory(next)
              if (next !== category) onApply({ category: next, matched_label: label.trim() || null, save_as_contact: saveAsContact })
            }}
            className="w-full"
          >
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
            to, so it gets the "Create a rule" section below instead.
            Toggling this also applies immediately (paired with whatever
            category/label are currently set), so it works whichever order
            the controls are used in. */}
        {row.is_paynow && (
          <label className="flex items-center gap-1.5 text-xs text-text pb-2 cursor-pointer">
            <Checkbox
              checked={saveAsContact}
              disabled={applyPending}
              onChange={(next) => {
                setSaveAsContact(next)
                onApply({ category, matched_label: label.trim() || null, save_as_contact: next })
              }}
            />
            Save as contact mapping
          </label>
        )}
      </div>
      {/* Deliberately its own row with its own button, not a checkbox bolted
          onto Apply above - applying a category to this one transaction and
          creating a rule that resolves every matching transaction going
          forward (including elsewhere in this same batch, via the rerun
          this triggers server-side) are two different actions with two
          different blast radii, so they get two different confirmations. */}
      {!row.is_paynow && (
        <div className="flex items-end gap-3 pt-3 border-t border-border/70">
          <div className="flex-1">
            <div className="text-2xs text-muted mb-1">
              Create a rule — future transactions containing this text will be categorized as{' '}
              <span className="text-text font-medium">{category}</span>
              {label.trim() && (
                <>
                  , labeled <span className="text-text font-medium">{label.trim()}</span>
                </>
              )}{' '}
              automatically
            </div>
            <input
              value={rulePattern}
              onChange={(e) => setRulePattern(e.target.value)}
              placeholder={row.raw_description}
              className="w-full box-border px-2.5 py-1.5 rounded-lg border border-border bg-input text-text text-xs font-mono"
            />
          </div>
          <button
            onClick={() => onCreateRule(rulePattern.trim(), category, label.trim() || null)}
            disabled={createRulePending || !rulePattern.trim()}
            className="shrink-0 inline-flex items-center gap-1.5 text-xs font-semibold px-3.5 py-2 rounded-lg border border-border bg-transparent text-text hover:bg-input cursor-pointer disabled:opacity-60 whitespace-nowrap"
          >
            <ListPlus size={13} className="shrink-0" />
            Create Rule
          </button>
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
  onCreateRule,
  createRulePending,
  onUndoRule,
  undoRulePending,
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
  onCreateRule: (
    row: ReviewRow,
    matchPattern: string,
    targetCategory: string,
    displayLabel: string | null,
  ) => Promise<{ rule_id: number; updated_rows: RuleRerunRowSnapshot[] }>
  createRulePending: boolean
  onUndoRule: (payload: { rule_id: number; rows: RuleRerunRowSnapshot[] }) => Promise<void>
  undoRulePending: boolean
  footer: ReactNode
  emptyMessage?: string
}) {
  const [openKey, setOpenKey] = useState<number | null>(null)
  const [ruleBanner, setRuleBanner] = useState<{
    ruleId: number
    rows: RuleRerunRowSnapshot[]
    matchPattern: string
    category: string
  } | null>(null)
  const categoriesQ = useCategories()

  // While AI categorization is running, its not-yet-resolved candidates get
  // pulled into their own group at the very top of the row list (highest
  // priority, above even already-resolved ai_suggested/needs_review rows),
  // sorted by date within the group - see isAiPending. The running banner
  // moves from a generic top-of-dialog notice to sitting right on this
  // group, so the "still working" state and the rows it's working on read
  // as one unit. If no rows currently qualify (e.g. they're all filtered
  // out as duplicates), fall back to the old top-of-dialog banner instead
  // of showing an empty group header.
  const aiPendingRows = aiStatus === 'running' ? rows.filter(isAiPending).sort(byDateDesc) : []
  const aiPendingKeys = new Set(aiPendingRows.map((r) => r.key))
  const otherRows = [...rows]
    .filter((r) => !aiPendingKeys.has(r.key))
    .sort((a, b) => Number(b.ai_suggested) - Number(a.ai_suggested) || byDateDesc(a, b))

  return (
    <Modal onClose={onClose} width={860}>
      <div className="flex items-start justify-between mb-0.5">
        <div>
          <div className="text-lg font-bold">{title}</div>
          <div className="text-md text-muted mt-0.5 mb-4 flex items-center gap-2 flex-wrap">
            <span>{subtitle}</span>
            {/* A persistent, always-visible status pill - unlike the group
                header/footer text below (which only appear while scrolled to
                the right spot, or only for specific states), this reflects
                every non-disabled aiStatus at a glance, including "done" -
                which otherwise had no banner of its own anywhere in this
                dialog once the running group disappeared. */}
            {aiStatus !== 'disabled' && (
              <span
                className="inline-flex items-center gap-1 text-2xs font-semibold px-2 py-0.5 rounded-full shrink-0"
                style={
                  aiStatus === 'failed'
                    ? { background: 'var(--color-danger-badge-bg)', color: 'var(--color-danger-badge-fg)' }
                    : aiStatus === 'done'
                      ? { background: SUCCESS_BG, color: SUCCESS_FG }
                      : { background: AI_BADGE_BG, color: AI_BADGE_FG }
                }
              >
                {aiStatus === 'running' && <Loader2 size={10} className="animate-spin shrink-0" />}
                {aiStatus === 'running' && 'AI categorizing…'}
                {aiStatus === 'done' && 'AI categorization complete'}
                {aiStatus === 'failed' && 'AI categorization failed'}
              </span>
            )}
          </div>
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
      {aiStatus === 'running' && aiPendingRows.length === 0 && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 flex items-center gap-2 text-xs"
          style={{ background: AI_BG, color: AI_BADGE_FG }}
        >
          <Loader2 size={14} className="animate-spin shrink-0" />
          AI is categorizing leftover transactions with {aiModel}… you can keep working, or close this and check
          back later.
        </div>
      )}
      {aiStatus === 'failed' && aiWarning && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 text-xs"
          style={{ background: 'var(--color-warning-surface)', color: 'var(--color-warning-text)' }}
        >
          {aiWarning}
        </div>
      )}

      {/* Confirms the "Create Rule" action and offers to back it out - a
          rule can retroactively recategorize other rows elsewhere in this
          same batch, so it gets its own persistent (non-fading) banner
          rather than the plain "popover just closes" feedback a regular
          Apply gets. Stays up until dismissed, undone, or replaced by a
          newer rule creation. */}
      {ruleBanner && (
        <div
          className="rounded-2lg px-4 py-2.5 mb-4 flex items-center justify-between gap-3 text-xs"
          style={{ background: SUCCESS_BG, color: SUCCESS_FG }}
        >
          <div>
            Rule created — "{ruleBanner.matchPattern}" now categorizes as{' '}
            <span className="font-semibold">{ruleBanner.category}</span>. Applied to {ruleBanner.rows.length}{' '}
            transaction{ruleBanner.rows.length === 1 ? '' : 's'} in this batch.
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={async () => {
                try {
                  await onUndoRule({ rule_id: ruleBanner.ruleId, rows: ruleBanner.rows })
                  setRuleBanner(null)
                } catch {
                  // leave the banner up so the user can retry the undo
                }
              }}
              disabled={undoRulePending}
              className="text-2xs font-semibold px-2.5 py-1.5 rounded-md bg-transparent cursor-pointer inline-flex items-center gap-1 disabled:opacity-60"
              style={{ color: SUCCESS_FG, border: '1px solid currentColor' }}
            >
              <Undo2 size={11} /> Undo
            </button>
            <button
              onClick={() => setRuleBanner(null)}
              className="text-base leading-none cursor-pointer border-none bg-transparent"
              style={{ color: SUCCESS_FG }}
            >
              ×
            </button>
          </div>
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
        <div className="grid grid-cols-[80px_1fr_180px_110px] px-5 py-2.5 text-2xs text-muted-2 uppercase tracking-wide border-b border-border/70 sticky top-0 bg-input">
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div className="text-right">Amount</div>
        </div>
        {rows.length === 0 && <EmptyState icon={Inbox} title={emptyMessage} />}
        {/* Every row is reviewable/clickable regardless of AI or needs_review
            state - adding a rule or contact mapping shouldn't be gated on
            whether AI touched the row. Base ordering is most-recent-first;
            layered on top, already-resolved ai_suggested rows are stably
            sorted to the top of the "rest" group so they're easy to find,
            and - while AI is still running - its not-yet-resolved
            candidates get pulled into their own group above everything
            else, with the "still working" banner riding along as that
            group's header instead of a separate dialog-wide notice. */}
        {aiPendingRows.length > 0 && (
          <div
            className="px-5 py-2 flex items-center gap-2 text-2xs border-b border-border/70"
            style={{ background: AI_BG, color: AI_BADGE_FG }}
          >
            <Loader2 size={12} className="animate-spin shrink-0" />
            AI is categorizing these {aiPendingRows.length} transaction{aiPendingRows.length === 1 ? '' : 's'} with{' '}
            {aiModel}… you can keep working, or close this and check back later.
          </div>
        )}
        {[...aiPendingRows, ...otherRows].map((row) => {
          const isOpen = openKey === row.key
          const current = aiIsCurrent(row)
          const pending = aiPendingKeys.has(row.key)
          const colorOverride = row.needs_review
            ? { bg: AMBER_BADGE_BG, fg: AMBER_BADGE_FG }
            : row.ai_suggested && current
              ? { bg: AI_BADGE_BG, fg: AI_BADGE_FG }
              : undefined
          const rowBg = pending
            ? AI_BG
            : row.needs_review
              ? AMBER_BG
              : row.ai_suggested && current
                ? AI_BG
                : undefined
          return (
            <div key={row.key}>
              <div
                onClick={() => setOpenKey(isOpen ? null : row.key)}
                className="grid grid-cols-[80px_1fr_180px_110px] items-center px-5 py-2.5 text-md border-b border-border/70 cursor-pointer"
                style={{ background: rowBg ?? (isOpen ? 'var(--color-input)' : undefined), opacity: pending ? 0.75 : undefined }}
              >
                <div className="text-muted font-mono text-xs">{fmtDate(row.transaction_date)}</div>
                <div className="min-w-0 pr-2 flex items-center gap-1.5">
                  {(row.ai_suggested || pending) && (
                    <Sparkles
                      size={11}
                      className={`shrink-0 ${pending ? 'animate-pulse' : ''}`}
                      style={{ color: current || pending ? AI_BADGE_FG : 'var(--color-muted-2)' }}
                    />
                  )}
                  <div className="min-w-0">
                    <div className="truncate">{row.matched_label ?? row.raw_description}</div>
                    {/* The clean label/AI suggestion is never the only thing shown - the
                        full raw bank description stays visible underneath it, not just
                        in a hover title, so it's never hidden behind an edited name. */}
                    {row.matched_label && (
                      <div className="truncate text-2xs text-muted-2" title={row.raw_description}>
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
                    // Deliberately doesn't close the popover on success (even
                    // on failure, there's nothing to undo here) - the whole
                    // point of auto-apply-on-change (category, label,
                    // save-as-contact, restore default) is that each control
                    // can be used independently without losing the others;
                    // forcing a close after the first one would cut that
                    // short. The row header's own click toggle is still how
                    // the user closes it when done.
                    try {
                      await onApplyRow(row, body)
                    } catch {
                      // swallow - nothing else to do here; the user can just retry
                    }
                  }}
                  createRulePending={createRulePending}
                  onCreateRule={async (matchPattern, targetCategory, displayLabel) => {
                    try {
                      const result = await onCreateRule(row, matchPattern, targetCategory, displayLabel)
                      setOpenKey(null)
                      setRuleBanner({
                        ruleId: result.rule_id,
                        rows: result.updated_rows,
                        matchPattern,
                        category: targetCategory,
                      })
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
