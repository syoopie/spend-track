import { useCurrentStagingBatch } from '../api/hooks'
import { fmtRelativeTime } from '../lib/format'
import { Button } from './Button'
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

  return (
    <div
      className="flex items-center justify-between gap-4 mx-9 mt-5 px-4.5 py-3 rounded-xl border"
      style={{ background: 'var(--color-warning-surface)', borderColor: 'var(--color-warning-surface-border)' }}
    >
      <div className="text-md" style={{ color: 'var(--color-warning-text)' }}>
        <span className="font-semibold">{filenameSummary}</span> — {batch.new_extracted} transaction
        {batch.new_extracted === 1 ? '' : 's'} awaiting review, staged {fmtRelativeTime(batch.created_at)}.
      </div>
      <Button variant="primary" size="sm" onClick={openReview} className="shrink-0">
        Review Now
      </Button>
    </div>
  )
}
