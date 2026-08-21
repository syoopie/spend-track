import { useState } from 'react'
import { useRecategorizeTransactions } from '../api/hooks'
import { fmtMonthRangeLabel } from '../lib/format'
import { Modal } from './Modal'

export function RecategorizeModal({
  range,
  accountId,
  onClose,
}: {
  range: { from: string; to: string }
  accountId?: string
  onClose: () => void
}) {
  const recategorize = useRecategorizeTransactions()
  const [result, setResult] = useState<{ scanned: number; changed: number } | null>(null)

  function handleConfirm() {
    recategorize.mutate(
      { date_from: range.from, date_to: range.to, account_id: accountId ?? null },
      {
        onSuccess: (data) => setResult({ scanned: data.transactions_scanned, changed: data.transactions_changed }),
      },
    )
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-[15px] font-semibold mb-2.5">Recategorize Transactions</div>

      {!result && (
        <>
          <div className="text-[13px] text-muted mb-4">
            Re-run every categorization rule against transactions from{' '}
            <span className="text-text font-medium">{fmtMonthRangeLabel(range.from, range.to)}</span>
            {accountId ? ' for the selected account' : ' across all accounts'}. This overwrites the current
            category, label, and exclusion status of any transaction in that range - including manual edits
            you've made - with what the current rules produce.
          </div>
          <div className="flex justify-end gap-2.5">
            <button
              onClick={onClose}
              className="text-[12px] px-3.5 py-2 rounded-lg border border-border bg-card text-text cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={recategorize.isPending}
              className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
            >
              {recategorize.isPending ? 'Recategorizing…' : 'Recategorize'}
            </button>
          </div>
        </>
      )}

      {result && (
        <>
          <div className="text-[13px] text-muted mb-4">
            Scanned <span className="text-text font-medium">{result.scanned}</span> transaction
            {result.scanned === 1 ? '' : 's'}, updated{' '}
            <span className="text-text font-medium">{result.changed}</span>.
          </div>
          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer"
            >
              Done
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
