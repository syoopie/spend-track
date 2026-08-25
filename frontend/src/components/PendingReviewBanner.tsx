import { Loader2 } from 'lucide-react'
import { useCurrentStagingBatch } from '../api/hooks'
import { fmtRelativeTime } from '../lib/format'
import { Button } from './Button'
import { ElapsedTimer } from './ElapsedTimer'
import { useUploadDialog } from './UploadProvider'

// Shown above every page's content (see App.tsx's MainLayout, which keeps
// this in a non-scrolling row above the scroll pane so it can never be
// scrolled out from under a page's own sticky header - DASH-6 in UI
// Review.dc.html), not just the Dashboard - a pending statement blocks a
// second upload app-wide (see UploadProvider's hasPendingBatch guard), so
// the prompt to go resolve it needs to be visible no matter which page the
// user happens to be on.
export function PendingReviewBanner() {
  const { openReview } = useUploadDialog()
  // Same ['staging-batch','current'] query UploadProvider already has
  // mounted - React Query dedupes this against that instance rather than
  // firing a second request, so reading the real batch here (filename,
  // count, staged-at) instead of just the boolean hasPendingBatch costs
  // nothing extra.
  const batchQ = useCurrentStagingBatch()
  const batch = batchQ.data
  if (!batch) return null

  const filenameSummary =
    batch.source_filenames.length === 1
      ? batch.source_filenames[0]
      : `${batch.source_filenames.length} statement files`

  // Distinct AI-tinted state (same colors ReviewDialog's own in-dialog
  // banner uses for this) rather than the plain "awaiting review" amber -
  // the two mean different things: amber says a human needs to look at
  // this, the AI state says a background job is still working and there's
  // nothing to review yet. Task 7 in this session's request list: the
  // banner previously looked identical in both states with no timer at all.
  const aiRunning = batch.ai_status === 'running'

  return (
    <div
      className="flex items-center justify-between gap-4 mx-9 mt-5 px-4.5 py-3 rounded-xl border"
      style={
        aiRunning
          ? { background: 'var(--color-ai-surface)', borderColor: 'var(--color-ai-surface-border)' }
          : { background: 'var(--color-warning-surface)', borderColor: 'var(--color-warning-surface-border)' }
      }
    >
      <div
        className="text-md flex items-center gap-2"
        style={{ color: aiRunning ? 'var(--color-ai-text)' : 'var(--color-warning-text)' }}
      >
        {aiRunning ? (
          <>
            <Loader2 size={14} className="animate-spin shrink-0" />
            <span>
              AI is categorizing <span className="font-semibold">{filenameSummary}</span> with {batch.ai_model}
              {batch.ai_started_at && (
                <>
                  {' '}
                  · <ElapsedTimer startedAt={batch.ai_started_at} />
                </>
              )}
            </span>
          </>
        ) : (
          <span>
            <span className="font-semibold">{filenameSummary}</span> — {batch.new_extracted} transaction
            {batch.new_extracted === 1 ? '' : 's'} awaiting review, staged {fmtRelativeTime(batch.created_at)}.
          </span>
        )}
      </div>
      <Button variant="primary" size="sm" onClick={openReview} className="shrink-0">
        {aiRunning ? 'View Progress' : 'Review Now'}
      </Button>
    </div>
  )
}
