import { useState } from 'react'
import { useBatchActions, useCurrentRecategorizeBatch, useRecategorizeTransactions } from '../api/hooks'
import { fmtMonthRangeLabel } from '../lib/format'
import { Button } from './Button'
import { ErrorState } from './EmptyState'
import { Modal } from './Modal'
import { ReviewDialog, type ReviewRow, type ReviewStatCard } from './ReviewDialog'

// The exact same review/commit/discard flow as staging's upload
// (StagingReviewDialog): the POST proposes a pending batch, nothing is
// written to the DB until Commit, and Discard - dismissible at any point,
// including mid-AI-categorization - throws the proposal away untouched.
export function RecategorizeReviewDialog({
  range,
  accountId,
  onClose,
}: {
  range: { from: string; to: string }
  accountId?: string
  onClose: () => void
}) {
  const recategorize = useRecategorizeTransactions()
  // Always check for an already-pending batch first (e.g. the user closed
  // this dialog earlier without committing/discarding, then reopened it via
  // the Recategorize button again) - only fall back to the confirm prompt
  // once we know for certain there isn't one.
  const batchQ = useCurrentRecategorizeBatch(true)
  // Hooks must run unconditionally regardless of which view below renders -
  // an empty batchId is inert until a batch actually exists.
  const actions = useBatchActions('recategorize', batchQ.data?.batch_id ?? '')
  const [confirmError, setConfirmError] = useState<string | null>(null)

  function handleConfirm() {
    setConfirmError(null)
    recategorize.mutate(
      { date_from: range.from, date_to: range.to, account_id: accountId ?? null },
      { onError: () => setConfirmError('Could not start recategorization. Please try again.') },
    )
  }

  if (batchQ.isLoading) {
    return (
      <Modal onClose={onClose} width={460}>
        <div className="text-muted text-sm">Loading…</div>
      </Modal>
    )
  }

  if (batchQ.isError) {
    return (
      <Modal onClose={onClose} width={420}>
        <ErrorState description="Couldn't check for a pending recategorization." onRetry={() => batchQ.refetch()} />
      </Modal>
    )
  }

  if (!batchQ.data) {
    return (
      <Modal onClose={onClose} width={420}>
        <div className="text-title-sm font-semibold mb-2.5">Recategorize Transactions</div>
        <div className="text-md text-muted mb-4">
          Re-run every categorization rule against transactions from{' '}
          <span className="text-text font-medium">{fmtMonthRangeLabel(range.from, range.to)}</span>
          {accountId ? ' for the selected account' : ' across all accounts'}. Nothing is applied until you review
          and commit — this proposes the recomputed category, label, and exclusion status for each transaction in
          that range (including ones you've manually edited before) without changing anything yet.
        </div>
        {confirmError && <div className="text-xs text-danger-text mb-3">{confirmError}</div>}
        <div className="flex justify-end gap-2.5">
          <Button size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" onClick={handleConfirm} disabled={recategorize.isPending}>
            {recategorize.isPending ? 'Scanning…' : 'Recategorize'}
          </Button>
        </div>
      </Modal>
    )
  }

  const batch = batchQ.data

  async function handleCommit() {
    await actions.commit(batch.batch_id)
    onClose()
  }

  async function handleDiscard() {
    await actions.discard(batch.batch_id)
    onClose()
  }

  const rows: ReviewRow[] = batch.rows.map((r) => ({
    key: r.key,
    transaction_date: r.transaction_date,
    raw_description: r.raw_description,
    matched_label: r.matched_label,
    amount: r.amount,
    category: r.category,
    subcategory: r.subcategory,
    is_excluded: r.is_excluded,
    exclusion_reason: r.exclusion_reason,
    needs_review: r.needs_review,
    is_paynow: r.is_paynow,
    original_category: r.original_category,
    original_label: r.original_label,
    ai_suggested: r.ai_suggested,
    ai_category: r.ai_category,
    ai_label: r.ai_label,
    ai_rule_pattern: r.ai_rule_pattern,
  }))

  const statCards: ReviewStatCard[] = [
    { label: 'Scanned', value: batch.scanned },
    { label: 'Proposed Changes', value: batch.changed },
    ...(batch.ai_suggested_count > 0
      ? [{ label: 'AI Suggested', value: batch.ai_suggested_count, tone: 'ai' as const }]
      : []),
  ]

  return (
    <ReviewDialog
      title="Recategorize Transactions"
      subtitle={`${fmtMonthRangeLabel(batch.date_from, batch.date_to)}${batch.account_id ? ' — selected account' : ' — all accounts'} — proposed, awaiting commit`}
      onClose={onClose}
      statCards={statCards}
      aiStatus={batch.ai_status}
      aiWarning={batch.ai_warning}
      aiModel={batch.ai_model}
      rows={rows}
      onApplyRow={(row, body) => actions.applyRow(row.key, body)}
      applyPending={actions.applyPending}
      onCreateRule={(_row, matchPattern, targetCategory, displayLabel) =>
        actions.createRule(matchPattern, targetCategory, displayLabel)
      }
      createRulePending={actions.createRulePending}
      onUndoRule={actions.undoRule}
      undoRulePending={actions.undoRulePending}
      emptyMessage="No transactions in this range."
      footer={
        <>
          {batch.ai_status === 'running' && (
            <div className="text-2xs text-muted mr-auto">
              AI categorization still running — you can commit once it finishes, or close this and check back
              later.
            </div>
          )}
          <Button variant="danger-outline" onClick={handleDiscard} disabled={actions.discardPending}>
            Discard
          </Button>
          <Button
            variant="primary"
            onClick={handleCommit}
            disabled={actions.commitPending || batch.rows.length === 0 || batch.ai_status === 'running'}
            title={batch.ai_status === 'running' ? 'Wait for AI categorization to finish, or close this dialog' : undefined}
          >
            Commit {batch.changed} Change{batch.changed === 1 ? '' : 's'}
          </Button>
        </>
      }
    />
  )
}
