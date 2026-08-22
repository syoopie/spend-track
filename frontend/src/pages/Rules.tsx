import { Pencil } from 'lucide-react'
import { useState } from 'react'
import { useCategories, useCreateRule, useDeleteRule, useReorderRules, useRules, useUpdateRule } from '../api/hooks'
import { CategoryBadge } from '../components/CategoryBadge'
import { categoryOptionElements } from '../components/CategoryOptions'
import { Checkbox } from '../components/Checkbox'
import { Modal } from '../components/Modal'
import { Select } from '../components/Select'
import type { CategoryDirection, Rule } from '../api/types'

function RuleFormModal({ rule, onClose }: { rule?: Rule; onClose: () => void }) {
  const categoriesQ = useCategories()
  const createRule = useCreateRule()
  const updateRule = useUpdateRule()
  const [pattern, setPattern] = useState(rule?.match_pattern ?? '')
  const [category, setCategory] = useState(rule?.target_category ?? '')
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
    <Modal onClose={onClose} width={460}>
      <div className="text-base font-bold mb-1">{rule ? 'Edit Rule' : 'New Rule'}</div>
      <div className="text-[12px] text-muted mb-4">Applies to every transaction whose description contains the text below.</div>

      <div className="flex flex-col gap-3.5">
        <div>
          <div className="text-xs text-muted mb-1">Description contains</div>
          <input
            autoFocus
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="e.g. NETFLIX"
            className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px]"
          />
        </div>

        <label className="flex items-center gap-2 cursor-pointer text-[13px]">
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

        {isExclusion && (
          <div className="flex flex-col gap-3.5">
            <div>
              <div className="text-xs text-muted mb-1">Exclusion reason</div>
              <input
                value={exclusionReason}
                onChange={(e) => setExclusionReason(e.target.value)}
                placeholder="e.g. Self-transfer between own accounts"
                className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px]"
              />
            </div>
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
              <div className="text-[11px] text-muted-2 mt-1">
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
            <div className="text-[11px] text-muted-2">Lower numbers are evaluated first</div>
          </div>
          <input
            type="number"
            value={priority}
            onChange={(e) => setPriority(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="auto"
            className="w-20 box-border px-2.5 py-2 rounded-lg border border-border bg-input text-text text-[13px] text-right"
          />
        </div>
      </div>

      <div className="flex justify-end gap-2.5 mt-5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !pattern.trim()}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          {rule ? 'Save Changes' : 'Save Rule'}
        </button>
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
  // 'new' opens the modal in Add mode; a Rule opens it pre-filled in Edit mode.
  const [formTarget, setFormTarget] = useState<Rule | 'new' | null>(null)
  const [draggedId, setDraggedId] = useState<number | null>(null)

  const rules = rulesQ.data ?? []

  function handleDrop(targetId: number) {
    if (draggedId == null) return
    const newOrder = reorder(rules, draggedId, targetId)
    setDraggedId(null)
    reorderRules.mutate(newOrder.map((r) => r.id))
  }

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="text-[22px] font-bold font-display">Categorization &amp; Exclusion Rules</div>
          <div className="text-[13px] text-muted mt-0.5">Evaluated top to bottom — the first match wins</div>
        </div>
        <button
          onClick={() => setFormTarget('new')}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer self-start"
        >
          + New Rule
        </button>
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {rulesQ.isLoading && <div className="p-5 text-muted text-sm">Loading…</div>}
        {!rulesQ.isLoading && rules.length === 0 && (
          <div className="p-5 text-muted text-sm">No rules yet — transactions fall back to contact matching, then "Others".</div>
        )}
        {rules.map((r) => {
          return (
            <div
              key={r.id}
              draggable
              onDragStart={() => setDraggedId(r.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDrop(r.id)}
              className="flex items-center gap-3.5 px-5 py-3.5 border-b border-divider group"
            >
              <span className="text-dim text-sm cursor-grab tracking-widest">⠿</span>
              <div className="w-6.5 h-6.5 rounded-md bg-input text-muted text-xs font-bold flex items-center justify-center shrink-0">
                {r.priority}
              </div>
              <div className="flex-1 text-[13px]">
                <span className="text-muted-2">IF</span> Transaction{' '}
                <span className="text-muted-2">CONTAINS</span>{' '}
                <span className="font-mono bg-input px-1.5 py-0.5 rounded">{r.match_pattern}</span>{' '}
                <span className="text-muted-2">THEN</span>{' '}
                {r.is_exclusion_rule ? (
                  <>
                    <span
                      className="text-[11px] font-semibold px-2 py-0.5 rounded-md"
                      style={{ background: 'oklch(28% 0.06 25)', color: 'oklch(75% 0.15 25)' }}
                    >
                      EXCLUDE
                    </span>
                    <span className="text-muted-2 text-[11px] uppercase tracking-wide ml-1.5">
                      {r.direction} only
                    </span>
                    <span className="text-muted-2 text-xs"> — {r.exclusion_reason}</span>
                  </>
                ) : (
                  <CategoryBadge category={r.target_category ?? ''} categories={categoriesQ.data} />
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
                onClick={() => deleteRule.mutate(r.id)}
                className="text-xs text-muted-2 hover:text-danger-text bg-transparent border-none cursor-pointer opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
              >
                Delete
              </button>
            </div>
          )
        })}
      </div>

      {formTarget && (
        <RuleFormModal rule={formTarget === 'new' ? undefined : formTarget} onClose={() => setFormTarget(null)} />
      )}
    </div>
  )
}
