import { useBatchActions, useCurrentStagingBatch } from '../api/hooks'
import { Button } from './Button'
import { ErrorState } from './EmptyState'
import { Modal } from './Modal'
import { ReviewDialog, type ReviewRow, type ReviewStatCard } from './ReviewDialog'

const SKELETON_ROW_COLS = 'grid-cols-[80px_1fr_180px_110px]'

// Three stat-card placeholders and eight shimmer rows at roughly the real
// row height, so the dialog doesn't visibly resize once data arrives -
// REV-7 in UI Review.dc.html. Replaces the old loading branch, which
// mounted a full ReviewDialog with no-op callbacks and empty stat
// cards - a functioning close button around an otherwise hollow shell.
// Kept its own close button for the same reason the old version did:
// nothing about a slow parse/AI pass should block dismissing the dialog.
function StagingReviewSkeleton({ onClose }: { onClose: () => void }) {
  return (
    <Modal onClose={onClose} width={860}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="h-[18px] w-64 bg-input rounded animate-pulse mb-2.5" />
          <div className="h-[13px] w-48 bg-input rounded animate-pulse" />
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-text text-lg leading-none cursor-pointer border-none bg-transparent"
        >
          ×
        </button>
      </div>
      <div className="flex gap-3 mb-5 flex-wrap">
        {[0, 1, 2].map((i) => (
          <div key={i} className="bg-input border border-border rounded-2lg px-4.5 py-3 w-[140px]">
            <div className="h-[11px] w-16 bg-border rounded animate-pulse mb-2.5" />
            <div className="h-[24px] w-10 bg-border rounded animate-pulse" />
          </div>
        ))}
      </div>
      <div className="bg-input border border-border rounded-xl overflow-hidden mb-5">
        <div className={`grid ${SKELETON_ROW_COLS} px-5 py-2.5 text-2xs text-muted-2 uppercase tracking-wide border-b border-border/70`}>
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div className="text-right">Amount</div>
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={`grid ${SKELETON_ROW_COLS} items-center px-5 py-2.5 border-b border-border/70`}>
            <div className="h-[13px] w-10 bg-border rounded animate-pulse" />
            <div className="h-[13px] bg-border rounded animate-pulse" style={{ width: `${55 + ((i * 13) % 30)}%` }} />
            <div className="h-[20px] w-24 bg-border rounded-full animate-pulse" />
            <div className="h-[13px] w-14 bg-border rounded animate-pulse ml-auto" />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-end gap-3">
        <div className="h-9 w-24 bg-input rounded-lg animate-pulse" />
        <div className="h-9 w-40 bg-input rounded-lg animate-pulse" />
      </div>
    </Modal>
  )
}

export function StagingReviewDialog({ onClose }: { onClose: () => void }) {
  const batchQ = useCurrentStagingBatch()
  const actions = useBatchActions('staging', batchQ.data?.batch_id ?? '')

  if (batchQ.isLoading) {
    return <StagingReviewSkeleton onClose={onClose} />
  }
  if (batchQ.isError) {
    return (
      <Modal onClose={onClose} width={420}>
        <ErrorState description="Couldn't load the staged batch." onRetry={() => batchQ.refetch()} />
      </Modal>
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
    original_category: r.original_category,
    original_label: r.original_label,
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
      onCreateRule={(_row, matchPattern, targetCategory, displayLabel) =>
        actions.createRule(matchPattern, targetCategory, displayLabel)
      }
      createRulePending={actions.createRulePending}
      onUndoRule={actions.undoRule}
      undoRulePending={actions.undoRulePending}
      emptyMessage="Nothing new to commit."
      footer={
        <>
          {batch.ai_status === 'running' && (
            <div className="text-2xs text-muted mr-auto">
              AI categorization still running — you can commit once it finishes, or close this and check back
              later.
            </div>
          )}
          <Button variant="danger-outline" onClick={handleDiscard} disabled={actions.discardPending}>
            Discard Batch
          </Button>
          <Button
            variant="primary"
            onClick={handleCommit}
            disabled={actions.commitPending || visibleRows.length === 0 || batch.ai_status === 'running'}
            title={batch.ai_status === 'running' ? 'Wait for AI categorization to finish, or close this dialog' : undefined}
          >
            Commit {batch.new_extracted} Transaction{batch.new_extracted === 1 ? '' : 's'}
          </Button>
        </>
      }
    />
  )
}
