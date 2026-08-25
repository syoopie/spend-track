import { ListChecks, Pencil, SlidersHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useCategories, useCreateRule, useDeleteRule, useReorderRules, useRules, useUpdateRule } from '../api/hooks'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { CategoryBadge } from '../components/CategoryBadge'
import { categoryOptionElements } from '../components/CategoryOptions'
import { Checkbox } from '../components/Checkbox'
import { EmptyState, ErrorState } from '../components/EmptyState'
import { Field, Input } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageShell } from '../components/PageShell'
import { Select } from '../components/Select'
import { useToast } from '../components/Toast'
import type { CategoryDirection, Rule } from '../api/types'

// How long a deleted rule stays hidden-but-recoverable before the delete
// actually reaches the backend (X-2 in UI Review.dc.html) - matches the
// toast's own duration so the undo option and the row's disappearance
// stay in sync.
const DELETE_UNDO_MS = 6000

// Rough client-side preview of the backend's fallback (engine/rules.py:
// `display_label or match_pattern.title()`) - not required to match Python's
// str.title() byte-for-byte, since it's only ever shown as a placeholder
// hint here, never actually sent or applied.
function titleCase(text: string): string {
  return text.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase())
}

function RuleFormModal({ rule, onClose }: { rule?: Rule; onClose: () => void }) {
  const categoriesQ = useCategories()
  const createRule = useCreateRule()
  const updateRule = useUpdateRule()
  const [pattern, setPattern] = useState(rule?.match_pattern ?? '')
  const [category, setCategory] = useState(rule?.target_category ?? '')
  const [displayLabel, setDisplayLabel] = useState(rule?.display_label ?? '')
  const [priority, setPriority] = useState<number | ''>(rule?.priority ?? '')
  const [isExclusion, setIsExclusion] = useState(rule?.is_exclusion_rule ?? false)
  const [exclusionReason, setExclusionReason] = useState(rule?.exclusion_reason ?? '')
  // Only meaningful (and sent to the backend) for an exclusion rule - a
  // category rule's direction is always just the direction of whichever
  // category it assigns, so the backend derives that on its own rather
  // than trusting a second, independently-editable copy of the same fact
  // that could drift out of sync with the category picked below.
  const [exclusionDirection, setExclusionDirection] = useState<CategoryDirection>(rule?.direction ?? 'outflow')

  async function handleSave() {
    if (!pattern.trim()) return
    const body = {
      match_pattern: pattern.trim(),
      target_category: isExclusion ? null : category || categoriesQ.data?.[0]?.name || 'Others',
      is_exclusion_rule: isExclusion,
      exclusion_reason: isExclusion ? exclusionReason.trim() || null : null,
      direction: isExclusion ? exclusionDirection : undefined,
      priority: priority === '' ? null : priority,
      display_label: isExclusion ? null : displayLabel.trim() || null,
    }
    if (rule) {
      await updateRule.mutateAsync({ id: rule.id, body })
    } else {
      await createRule.mutateAsync(body)
    }
    onClose()
  }

  const saving = createRule.isPending || updateRule.isPending

  return (
    <Modal onClose={onClose} width={460} title={rule ? 'Edit Rule' : 'New Rule'}>
      <div className="text-xs text-muted mb-4 -mt-2.5">
        Applies to every transaction whose description contains the text below.
      </div>

      <div className="flex flex-col gap-3.5">
        <Field label="Description contains">
          <Input autoFocus value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder="e.g. NETFLIX" />
        </Field>

        <label className="flex items-center gap-2 cursor-pointer text-md">
          <Checkbox checked={isExclusion} onChange={setIsExclusion} />
          Exclude these transactions instead of categorizing them
        </label>

        <div className="h-px bg-border" />

        {!isExclusion && (
          <div>
            <div className="text-xs text-muted mb-1">Category</div>
            <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full">
              <option value="">Select category…</option>
              {categoryOptionElements(categoriesQ.data)}
            </Select>
          </div>
        )}

        {!isExclusion && (
          <Field
            label="Display name (optional)"
            hint='Shown instead of the raw bank description for matching transactions. Leave blank to just title-case the pattern above.'
          >
            <Input
              value={displayLabel}
              onChange={(e) => setDisplayLabel(e.target.value)}
              placeholder={pattern.trim() ? titleCase(pattern.trim()) : 'e.g. Netflix'}
            />
          </Field>
        )}

        {isExclusion && (
          <div className="flex flex-col gap-3.5">
            <Field label="Exclusion reason">
              <Input
                value={exclusionReason}
                onChange={(e) => setExclusionReason(e.target.value)}
                placeholder="e.g. Self-transfer between own accounts"
              />
            </Field>
            <div>
              <div className="text-xs text-muted mb-1">Applies to</div>
              <Select
                value={exclusionDirection}
                onChange={(e) => setExclusionDirection(e.target.value as CategoryDirection)}
                className="w-full"
              >
                <option value="outflow">Outflow transactions only</option>
                <option value="inflow">Inflow transactions only</option>
              </Select>
              <div className="text-2xs text-muted-2 mt-1">
                An exclusion rule has no category to imply a direction from, so this must be picked explicitly -
                otherwise a pattern like a self-transfer's description could exclude both legs of an unrelated
                transaction pair.
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs text-muted">Priority</div>
            <div className="text-2xs text-muted-2">Lower numbers are evaluated first</div>
          </div>
          <Input
            fullWidth={false}
            type="number"
            value={priority}
            onChange={(e) => setPriority(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="auto"
            className="w-20 text-right"
          />
        </div>
      </div>

      <div className="flex justify-end gap-2.5 mt-5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={handleSave} disabled={saving || !pattern.trim()}>
          {rule ? 'Save Changes' : 'Save Rule'}
        </Button>
      </div>
    </Modal>
  )
}

function reorder(list: Rule[], draggedId: number, targetId: number): Rule[] {
  const dragIdx = list.findIndex((r) => r.id === draggedId)
  const targetIdx = list.findIndex((r) => r.id === targetId)
  if (dragIdx === -1 || targetIdx === -1 || dragIdx === targetIdx) return list
  const copy = [...list]
  const [item] = copy.splice(dragIdx, 1)
  copy.splice(targetIdx, 0, item)
  return copy
}

export function Rules() {
  const rulesQ = useRules()
  const categoriesQ = useCategories()
  const reorderRules = useReorderRules()
  const deleteRule = useDeleteRule()
  const toast = useToast()
  // 'new' opens the modal in Add mode; a Rule opens it pre-filled in Edit mode.
  const [formTarget, setFormTarget] = useState<Rule | 'new' | null>(null)
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverId, setDragOverId] = useState<number | null>(null)
  // Optimistically hidden rows whose actual delete is still deferred (see
  // handleDelete below) - kept separate from the query cache itself so
  // reorder's own ordered_ids composition (which the backend rejects
  // unless it names every non-default rule, deleted-but-not-yet-committed
  // included) stays correct.
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<number>>(new Set())
  const deleteTimers = useRef(new Map<number, ReturnType<typeof setTimeout>>())
  useEffect(() => {
    const timers = deleteTimers
    return () => {
      for (const t of timers.current.values()) clearTimeout(t)
    }
  }, [])

  const rules = rulesQ.data ?? []
  const visibleRules = rules.filter((r) => !pendingDeleteIds.has(r.id))

  function handleDrop(targetId: number) {
    if (draggedId == null) return
    const newOrder = reorder(rules, draggedId, targetId)
    setDraggedId(null)
    setDragOverId(null)
    reorderRules.mutate(newOrder.map((r) => r.id))
  }

  // Alt+Up/Alt+Down swaps a rule with its neighbour (X-2's keyboard
  // reordering) - drag-and-drop was previously the only way to reorder at
  // all.
  function moveRule(id: number, direction: -1 | 1) {
    const idx = rules.findIndex((r) => r.id === id)
    const targetIdx = idx + direction
    if (idx === -1 || targetIdx < 0 || targetIdx >= rules.length) return
    const copy = [...rules]
    const [item] = copy.splice(idx, 1)
    copy.splice(targetIdx, 0, item)
    reorderRules.mutate(copy.map((r) => r.id))
  }

  // Removes the row immediately and shows an undo toast; the real DELETE
  // only fires after the undo window passes (X-2 in UI Review.dc.html) -
  // before this, deleting was instant and unrecoverable.
  function handleDelete(rule: Rule) {
    setPendingDeleteIds((prev) => new Set(prev).add(rule.id))
    const timer = setTimeout(() => {
      deleteTimers.current.delete(rule.id)
      deleteRule.mutate(rule.id, {
        onError: () => {
          // The optimistic removal turned out to be wrong - un-hide the
          // row rather than lose it silently (useDeleteRule's onError
          // already toasts the failure).
          setPendingDeleteIds((prev) => {
            const next = new Set(prev)
            next.delete(rule.id)
            return next
          })
        },
      })
    }, DELETE_UNDO_MS)
    deleteTimers.current.set(rule.id, timer)
    toast.success(`Rule deleted — "${rule.display_label ?? rule.match_pattern}"`, {
      durationMs: DELETE_UNDO_MS,
      action: {
        label: 'Undo',
        onClick: () => {
          clearTimeout(deleteTimers.current.get(rule.id))
          deleteTimers.current.delete(rule.id)
          setPendingDeleteIds((prev) => {
            const next = new Set(prev)
            next.delete(rule.id)
            return next
          })
        },
      },
    })
  }

  return (
    <PageShell
      title="Categorization & Exclusion Rules"
      subtitle="Evaluated top to bottom — the first match wins"
      icon={SlidersHorizontal}
      actions={
        <Button variant="primary" onClick={() => setFormTarget('new')}>
          + New Rule
        </Button>
      }
    >
      <Card padding="" className="overflow-hidden">
        {rulesQ.isLoading && <div className="p-5 text-muted text-sm">Loading…</div>}
        {rulesQ.isError && <ErrorState description="Couldn't load your rules." onRetry={() => rulesQ.refetch()} />}
        {rulesQ.isSuccess && visibleRules.length === 0 && (
          <EmptyState
            icon={ListChecks}
            title="No rules yet"
            description='Transactions fall back to contact matching, then the built-in default rules, then "Others".'
            action={
              <Button variant="primary" size="sm" onClick={() => setFormTarget('new')}>
                + New Rule
              </Button>
            }
          />
        )}
        {visibleRules.map((r) => {
          return (
            <div
              key={r.id}
              draggable
              onDragStart={() => setDraggedId(r.id)}
              onDragOver={(e) => {
                e.preventDefault()
                if (draggedId != null && draggedId !== r.id) setDragOverId(r.id)
              }}
              onDragLeave={() => setDragOverId((id) => (id === r.id ? null : id))}
              onDrop={() => handleDrop(r.id)}
              onDragEnd={() => {
                setDraggedId(null)
                setDragOverId(null)
              }}
              className={`relative flex items-center gap-3.5 px-5 py-3.5 border-b border-divider group ${draggedId === r.id ? 'opacity-40' : ''}`}
            >
              {/* A 2px accent drop indicator, not a silent re-jump once the
                  round trip finishes (X-2) - shown on whichever row is
                  currently being dragged over. */}
              {dragOverId === r.id && draggedId !== r.id && (
                <div className="absolute -top-px left-0 right-0 h-0.5 bg-accent" />
              )}
              <span
                role="button"
                tabIndex={0}
                aria-label={`Reorder rule - Alt+Up or Alt+Down to move "${r.display_label ?? r.match_pattern}"`}
                onKeyDown={(e) => {
                  if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
                    e.preventDefault()
                    moveRule(r.id, e.key === 'ArrowUp' ? -1 : 1)
                  }
                }}
                className="text-dim text-sm cursor-grab tracking-widest rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
              >
                ⠿
              </span>
              <div className="w-6.5 h-6.5 rounded-md bg-input text-muted text-xs font-bold flex items-center justify-center shrink-0">
                {r.priority}
              </div>
              <div className="flex-1 text-md">
                <span className="text-muted-2">IF</span> Transaction{' '}
                <span className="text-muted-2">CONTAINS</span>{' '}
                <span className="font-mono bg-input px-1.5 py-0.5 rounded">{r.match_pattern}</span>{' '}
                <span className="text-muted-2">THEN</span>{' '}
                {r.is_exclusion_rule ? (
                  <>
                    <span
                      className="text-2xs font-semibold px-2 py-0.5 rounded-md"
                      style={{ background: 'var(--color-danger-badge-bg)', color: 'var(--color-danger-badge-fg)' }}
                    >
                      EXCLUDE
                    </span>
                    <span className="text-muted-2 text-2xs uppercase tracking-wide ml-1.5">
                      {r.direction} only
                    </span>
                    <span className="text-muted-2 text-xs"> — {r.exclusion_reason}</span>
                  </>
                ) : (
                  <>
                    <CategoryBadge category={r.target_category ?? ''} categories={categoriesQ.data} />
                    {r.display_label && (
                      <span className="text-muted-2 text-xs ml-1.5">
                        as <span className="text-text-2 font-medium">{r.display_label}</span>
                      </span>
                    )}
                  </>
                )}
              </div>
              <button
                onClick={() => setFormTarget(r)}
                title="Edit rule"
                className="text-muted-2 hover:text-text bg-transparent border-none cursor-pointer p-1 rounded-md opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                <Pencil size={13} />
              </button>
              <button
                onClick={() => handleDelete(r)}
                className="text-xs text-muted-2 hover:text-danger-text bg-transparent border-none cursor-pointer opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                Delete
              </button>
            </div>
          )
        })}
      </Card>

      {formTarget && (
        <RuleFormModal rule={formTarget === 'new' ? undefined : formTarget} onClose={() => setFormTarget(null)} />
      )}
    </PageShell>
  )
}
