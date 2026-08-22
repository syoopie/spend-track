import { useBatchActions, useCurrentStagingBatch } from '../api/hooks'
import { ReviewDialog, type ReviewRow, type ReviewStatCard } from './ReviewDialog'

export function StagingReviewDialog({ onClose }: { onClose: () => void }) {
  const batchQ = useCurrentStagingBatch()
  const actions = useBatchActions('staging', batchQ.data?.batch_id ?? '')

  if (batchQ.isLoading) {
    return (
      <ReviewDialog
        title="Staging & Pre-Commit Review"
        subtitle="Loading staged transactions…"
        onClose={onClose}
        statCards={[]}
        aiStatus="disabled"
        aiWarning={null}
        aiModel={null}
        rows={[]}
        onApplyRow={async () => {}}
        applyPending={false}
        onCreateRule={async () => ({ rule_id: 0, updated_rows: [] })}
        createRulePending={false}
        onUndoRule={async () => {}}
        undoRulePending={false}
        footer={null}
      />
    )
  }
  if (!batchQ.data) return null

  const batch = batchQ.data
  const visibleRows = batch.rows.filter((r) => !r.is_duplicate)

  async function handleCommit() {
    await actions.commit(batch.batch_id)
    onClose()
  }

  async function handleDiscard() {
    await actions.discard(batch.batch_id)
    onClose()
  }

  const rows: ReviewRow[] = visibleRows.map((r) => ({
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
    ai_suggested: r.ai_suggested,
    ai_category: r.ai_category,
    ai_label: r.ai_label,
    ai_rule_pattern: r.ai_rule_pattern,
  }))

  const statCards: ReviewStatCard[] = [
    { label: 'New Extracted', value: batch.new_extracted },
    { label: 'Duplicates Skipped', value: batch.duplicates_skipped, tone: 'muted' },
    { label: 'New Accounts Provisioned', value: batch.new_accounts_provisioned },
    ...(batch.needs_category_count > 0
      ? [{ label: 'PayNow — Needs Review', value: batch.needs_category_count, tone: 'amber' as const }]
      : []),
    ...(batch.ai_suggested_count > 0
      ? [{ label: 'AI Suggested', value: batch.ai_suggested_count, tone: 'ai' as const }]
      : []),
  ]

  return (
    <ReviewDialog
      title="Staging & Pre-Commit Review"
      subtitle={`${batch.source_filenames.join(', ')} — parsed, awaiting commit`}
      onClose={onClose}
      statCards={statCards}
      aiStatus={batch.ai_status}
      aiWarning={batch.ai_warning}
      aiModel={batch.ai_model}
      rows={rows}
      onApplyRow={(row, body) => actions.applyRow(row.key, body)}
      applyPending={actions.applyPending}
      onCreateRule={(_row, matchPattern, targetCategory) => actions.createRule(matchPattern, targetCategory)}
      createRulePending={actions.createRulePending}
      onUndoRule={actions.undoRule}
      undoRulePending={actions.undoRulePending}
      emptyMessage="Nothing new to commit."
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
            disabled={actions.discardPending}
            className="text-[13px] font-semibold px-4.5 py-2.5 rounded-lg cursor-pointer bg-input disabled:opacity-60"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Discard Batch
          </button>
          <button
            onClick={handleCommit}
            disabled={actions.commitPending || visibleRows.length === 0 || batch.ai_status === 'running'}
            title={batch.ai_status === 'running' ? 'Wait for AI categorization to finish, or close this dialog' : undefined}
            className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
          >
            Commit {batch.new_extracted} Transaction{batch.new_extracted === 1 ? '' : 's'}
          </button>
        </>
      }
    />
  )
}
