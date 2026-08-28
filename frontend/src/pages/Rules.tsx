import { ListChecks, Pencil, SlidersHorizontal, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useCategories, useCreateRule, useDeleteRule, useReorderRules, useRules, useUpdateRule } from '../api/hooks'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { CategoryBadge } from '../components/CategoryBadge'
import { EmptyState, ErrorState } from '../components/EmptyState'
import { PageShell } from '../components/PageShell'
import { RuleFormModal, type RuleFormSubmitValues } from '../components/RuleFormModal'
import type { Rule } from '../api/types'
import { useUndoableDelete } from '../lib/useUndoableDelete'

function RuleModal({ rule, onClose }: { rule?: Rule; onClose: () => void }) {
  const createRule = useCreateRule()
  const updateRule = useUpdateRule()

  async function handleSubmit(body: RuleFormSubmitValues) {
    if (rule) {
      await updateRule.mutateAsync({ id: rule.id, body })
    } else {
      await createRule.mutateAsync(body)
    }
  }

  return (
    <RuleFormModal
      rule={rule}
      onSubmit={handleSubmit}
      saving={createRule.isPending || updateRule.isPending}
      onClose={onClose}
    />
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
  // 'new' opens the modal in Add mode; a Rule opens it pre-filled in Edit mode.
  const [formTarget, setFormTarget] = useState<Rule | 'new' | null>(null)
  const [draggedId, setDraggedId] = useState<number | null>(null)
  const [dragOverId, setDragOverId] = useState<number | null>(null)
  const { pendingIds, requestDelete } = useUndoableDelete('Rule', deleteRule.mutate)

  const rules = rulesQ.data ?? []
  const visibleRules = rules.filter((r) => !pendingIds.has(r.id))

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
                className="text-muted-2 hover:text-text bg-transparent border-none cursor-pointer p-1 rounded-md opacity-40 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                <Pencil size={13} />
              </button>
              <button
                onClick={() => requestDelete(r.id, r.display_label ?? r.match_pattern)}
                title="Delete rule"
                aria-label="Delete rule"
                className="text-muted-2 hover:text-danger-text bg-transparent border-none cursor-pointer p-1 rounded-md opacity-40 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                <Trash2 size={13} />
              </button>
            </div>
          )
        })}
      </Card>

      {formTarget && (
        <RuleModal rule={formTarget === 'new' ? undefined : formTarget} onClose={() => setFormTarget(null)} />
      )}
    </PageShell>
  )
}
