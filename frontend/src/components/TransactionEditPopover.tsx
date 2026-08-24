import { useState } from 'react'
import { useCategories, useUpdateTransaction } from '../api/hooks'
import type { Transaction } from '../api/types'
import { categoryIcon } from '../lib/categoryColor'
import { Button } from './Button'
import { Checkbox } from './Checkbox'
import { Select } from './Select'

export function TransactionEditPopover({
  transaction,
  onClose,
}: {
  transaction: Transaction
  onClose: () => void
}) {
  const categoriesQ = useCategories()
  const updateTx = useUpdateTransaction()
  const [category, setCategory] = useState(transaction.category)
  const [label, setLabel] = useState(transaction.matched_label ?? '')
  const [isExcluded, setIsExcluded] = useState(transaction.is_excluded)
  const [exclusionReason, setExclusionReason] = useState(transaction.exclusion_reason ?? '')

  // Categories are direction-locked (see api/types.ts's CategoryDirection) -
  // an inflow transaction (a refund, a salary credit, ...) can only be
  // reassigned to an inflow category, and vice versa, so the picker only
  // ever offers the set that actually matches this transaction's sign.
  const direction = transaction.amount > 0 ? 'inflow' : 'outflow'
  const categoryOptions = (categoriesQ.data ?? []).filter((c) => c.direction === direction)
  const currentCategoryKnown = categoryOptions.some((c) => c.name === category)

  function handleSave() {
    updateTx.mutate(
      {
        id: transaction.id,
        body: {
          category,
          matched_label: label.trim() || null,
          is_excluded: isExcluded,
          exclusion_reason: isExcluded ? exclusionReason.trim() || null : null,
        },
      },
      { onSuccess: onClose },
    )
  }

  return (
    <div className="px-5 py-4 flex flex-col gap-3 border-b border-divider bg-input">
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="text-2xs text-muted mb-1">Display Name</div>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={transaction.raw_description}
            className="w-full box-border text-md px-2.5 py-1.5 rounded-md border border-border bg-card text-text"
          />
        </div>
        <div className="w-[220px]">
          <div className="text-2xs text-muted mb-1">Category · {direction === 'inflow' ? 'Inflow' : 'Outflow'}</div>
          <Select uiSize="sm" bg="card" value={category} onChange={(e) => setCategory(e.target.value)} className="w-full">
            {!currentCategoryKnown && <option value={category}>{category}</option>}
            {categoryOptions.map((c) => {
              const Icon = categoryIcon(categoryOptions, c.name)
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
      </div>
      <label className="flex items-center gap-2 text-xs text-text cursor-pointer">
        <Checkbox checked={isExcluded} onChange={setIsExcluded} />
        Exclude from totals
      </label>
      {isExcluded && (
        <input
          value={exclusionReason}
          onChange={(e) => setExclusionReason(e.target.value)}
          placeholder="Exclusion reason (e.g. self-transfer)"
          className="w-full box-border text-md px-2.5 py-1.5 rounded-md border border-border bg-card text-text"
        />
      )}
      <div className="flex justify-end gap-2.5">
        <Button size="sm" onClick={onClose}>Cancel</Button>
        <Button variant="primary" size="sm" onClick={handleSave} disabled={updateTx.isPending}>
          {updateTx.isPending ? 'Saving…' : 'Save'}
        </Button>
      </div>
    </div>
  )
}
