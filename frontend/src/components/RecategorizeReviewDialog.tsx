import { useState } from 'react'
import {
  useCommitRecategorizeBatch,
  useCreateRuleFromRecategorizeBatch,
  useCurrentRecategorizeBatch,
  useDiscardRecategorizeBatch,
  useRecategorizeTransactions,
  useUndoRuleFromRecategorizeBatch,
  useUpdateRecategorizeRow,
} from '../api/hooks'
import { fmtMonthRangeLabel } from '../lib/format'
import { Modal } from './Modal'
import { ReviewDialog, type ApplyRowBody, type ReviewRow, type ReviewStatCard } from './ReviewDialog'

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
  const commit = useCommitRecategorizeBatch()
  const discard = useDiscardRecategorizeBatch()
  // Hooks must run unconditionally regardless of which view below renders -
  // an empty batchId is inert until a batch actually exists.
  const updateRow = useUpdateRecategorizeRow(batchQ.data?.batch_id ?? '')
  const createRule = useCreateRuleFromRecategorizeBatch(batchQ.data?.batch_id ?? '')
  const undoRule = useUndoRuleFromRecategorizeBatch(batchQ.data?.batch_id ?? '')
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

  if (!batchQ.data) {
    return (
      <Modal onClose={onClose} width={420}>
        <div className="text-[15px] font-semibold mb-2.5">Recategorize Transactions</div>
        <div className="text-[13px] text-muted mb-4">
          Re-run every categorization rule against transactions from{' '}
          <span className="text-text font-medium">{fmtMonthRangeLabel(range.from, range.to)}</span>
          {accountId ? ' for the selected account' : ' across all accounts'}. Nothing is applied until you review
          and commit — this proposes the recomputed category, label, and exclusion status for each transaction in
          that range (including ones you've manually edited before) without changing anything yet.
        </div>
        {confirmError && <div className="text-[12px] text-danger-text mb-3">{confirmError}</div>}
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
            {recategorize.isPending ? 'Scanning…' : 'Recategorize'}
          </button>
        </div>
      </Modal>
    )
  }

  const batch = batchQ.data

  async function handleCommit() {
    await commit.mutateAsync(batch.batch_id)
    onClose()
  }

  async function handleDiscard() {
    await discard.mutateAsync(batch.batch_id)
    onClose()
  }

  async function handleApplyRow(row: ReviewRow, body: ApplyRowBody) {
    await updateRow.mutateAsync({
      transactionId: row.key,
      body: {
        category: body.category,
        save_as_contact: body.save_as_contact,
        contact_name: body.contact_name,
        contact_identifier: body.contact_identifier,
        reject_ai: body.reject_ai,
        restore_ai: body.restore_ai,
      },
    })
  }

  async function handleCreateRule(_row: ReviewRow, matchPattern: string, targetCategory: string) {
    return createRule.mutateAsync({ match_pattern: matchPattern, target_category: targetCategory })
  }

  const rows: ReviewRow[] = batch.rows.map((r) => ({
    key: r.transaction_id,
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
      onApplyRow={handleApplyRow}
      applyPending={updateRow.isPending}
      onCreateRule={handleCreateRule}
      createRulePending={createRule.isPending}
      onUndoRule={(payload) => undoRule.mutateAsync(payload).then(() => {})}
      undoRulePending={undoRule.isPending}
      emptyMessage="No transactions in this range."
      footer={
        <>
          {batch.ai_status === 'running' && (
            <div className="text-[11px] text-muted mr-auto">
              AI categorization still running — you can commit once it finishes, or close this and check back
              later.
            </div>
          )}
          <button
            onClick={handleDiscard}
            disabled={discard.isPending}
            className="text-[13px] font-semibold px-4.5 py-2.5 rounded-lg cursor-pointer bg-input disabled:opacity-60"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Discard
          </button>
          <button
            onClick={handleCommit}
            disabled={commit.isPending || batch.rows.length === 0 || batch.ai_status === 'running'}
            title={batch.ai_status === 'running' ? 'Wait for AI categorization to finish, or close this dialog' : undefined}
            className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
          >
            Commit {batch.changed} Change{batch.changed === 1 ? '' : 's'}
          </button>
        </>
      }
    />
  )
}
