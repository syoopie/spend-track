import { useState } from 'react'
import { useCategories, useCreateRule, useDeleteRule, useReorderRules, useRules } from '../api/hooks'
import { Modal } from '../components/Modal'
import { categoryColor } from '../lib/categoryColor'
import type { Rule } from '../api/types'

function RuleBuilderModal({ onClose }: { onClose: () => void }) {
  const categoriesQ = useCategories()
  const createRule = useCreateRule()
  const [pattern, setPattern] = useState('')
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState<number | ''>('')
  const [isExclusion, setIsExclusion] = useState(false)
  const [exclusionReason, setExclusionReason] = useState('')

  async function handleSave() {
    if (!pattern.trim()) return
    await createRule.mutateAsync({
      match_pattern: pattern.trim(),
      target_category: isExclusion ? null : category || categoriesQ.data?.[0]?.name || 'Others',
      is_exclusion_rule: isExclusion,
      exclusion_reason: isExclusion ? exclusionReason.trim() || null : null,
      priority: priority === '' ? null : priority,
    })
    onClose()
  }

  return (
    <Modal onClose={onClose} width={460}>
      <div className="text-base font-bold mb-4">New Rule</div>
      <div className="text-[13px] text-[#c6c6cf] flex flex-col gap-3 mb-3.5">
        <div className="flex items-center gap-2">
          <span className="text-muted-2 w-[70px]">IF</span>
          <span className="w-[110px]">Transaction</span>
          <span className="text-muted-2">CONTAINS</span>
          <input
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="e.g. NETFLIX"
            className="flex-1 box-border px-2.5 py-2 rounded-md border border-border bg-input text-text text-[13px]"
          />
        </div>
        {!isExclusion && (
          <div className="flex items-center gap-2">
            <span className="text-muted-2 w-[70px]">THEN SET</span>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="flex-1 px-2.5 py-2 rounded-md border border-border bg-input text-text text-[13px]"
            >
              <option value="">Select category…</option>
              {(categoriesQ.data ?? []).map((c) => (
                <option key={c.id} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex items-center gap-2">
          <span className="text-muted-2 w-[70px]">PRIORITY</span>
          <input
            type="number"
            value={priority}
            onChange={(e) => setPriority(e.target.value === '' ? '' : Number(e.target.value))}
            placeholder="auto"
            className="w-[70px] box-border px-2.5 py-2 rounded-md border border-border bg-input text-text text-[13px] outline-none focus:border-accent"
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={isExclusion} onChange={(e) => setIsExclusion(e.target.checked)} />
          This is an exclusion rule
        </label>
        {isExclusion && (
          <div>
            <div className="text-xs text-muted-2 mb-1">Exclusion Reason</div>
            <input
              value={exclusionReason}
              onChange={(e) => setExclusionReason(e.target.value)}
              placeholder="e.g. Self-transfer between own accounts"
              className="w-full box-border px-2.5 py-2 rounded-md border border-border bg-input text-text text-[13px]"
            />
          </div>
        )}
      </div>
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={createRule.isPending || !pattern.trim()}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Save Rule
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
  const [modalOpen, setModalOpen] = useState(false)
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
          <div className="text-[22px] font-bold">Categorization &amp; Exclusion Rules</div>
          <div className="text-[13px] text-muted mt-0.5">Evaluated top to bottom — the first match wins</div>
        </div>
        <button
          onClick={() => setModalOpen(true)}
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
          const cc = categoryColor(categoriesQ.data, r.target_category ?? '')
          return (
            <div
              key={r.id}
              draggable
              onDragStart={() => setDraggedId(r.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => handleDrop(r.id)}
              className="flex items-center gap-3.5 px-5 py-3.5 border-b border-[#24252e] group"
            >
              <span className="text-[#3a3b48] text-sm cursor-grab tracking-widest">⠿</span>
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
                    <span className="text-muted-2 text-xs"> — {r.exclusion_reason}</span>
                  </>
                ) : (
                  <span className="text-[11px] px-2 py-0.5 rounded-md" style={{ background: cc.bg, color: cc.fg }}>
                    {r.target_category}
                  </span>
                )}
              </div>
              <button
                onClick={() => deleteRule.mutate(r.id)}
                className="text-xs text-muted-2 hover:text-danger-text bg-transparent border-none cursor-pointer opacity-0 group-hover:opacity-100"
              >
                Delete
              </button>
            </div>
          )
        })}
      </div>

      {modalOpen && <RuleBuilderModal onClose={() => setModalOpen(false)} />}
    </div>
  )
}
