import { useState } from 'react'
import { useCategories, useUpdateTransaction } from '../api/hooks'
import type { Transaction } from '../api/types'
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

  const categoryOptions = categoriesQ.data ?? []
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
    <div className="px-5 py-4 flex flex-col gap-3 border-b border-[#24252e] bg-input">
      <div className="flex items-end gap-3">
        <div className="flex-1">
          <div className="text-[11px] text-muted mb-1">Display Name</div>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={transaction.raw_description}
            className="w-full box-border text-[13px] px-2.5 py-1.5 rounded-md border border-border bg-card text-text"
          />
        </div>
        <div className="w-[220px]">
          <div className="text-[11px] text-muted mb-1">Category</div>
          <Select uiSize="sm" bg="card" value={category} onChange={(e) => setCategory(e.target.value)} className="w-full">
            {!currentCategoryKnown && <option value={category}>{category}</option>}
            {categoryOptions.map((c) => (
              <option key={c.id} value={c.name}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <label className="flex items-center gap-2 text-[12px] text-text cursor-pointer">
        <Checkbox checked={isExcluded} onChange={setIsExcluded} />
        Exclude from totals
      </label>
      {isExcluded && (
        <input
          value={exclusionReason}
          onChange={(e) => setExclusionReason(e.target.value)}
          placeholder="Exclusion reason (e.g. self-transfer)"
          className="w-full box-border text-[13px] px-2.5 py-1.5 rounded-md border border-border bg-card text-text"
        />
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[12px] px-3.5 py-2 rounded-lg border border-border bg-card text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={updateTx.isPending}
          className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          {updateTx.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
