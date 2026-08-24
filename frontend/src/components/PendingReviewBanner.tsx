import { Button } from './Button'
import { useUploadDialog } from './UploadProvider'

// Shown above every page's content (see App.tsx's MainLayout), not just the
// Dashboard - a pending statement blocks a second upload app-wide (see
// UploadProvider's hasPendingBatch guard), so the prompt to go resolve it
// needs to be visible no matter which page the user happens to be on.
export function PendingReviewBanner() {
  const { hasPendingBatch, openReview } = useUploadDialog()
  if (!hasPendingBatch) return null

  return (
    <div
      className="flex items-center justify-between gap-4 mx-9 mt-5 px-4.5 py-3 rounded-xl border"
      style={{ background: 'var(--color-warning-surface)', borderColor: 'var(--color-warning-surface-border)' }}
    >
      <div className="text-md" style={{ color: 'var(--color-warning-text)' }}>
        A statement is awaiting review before it can be committed.
      </div>
      <Button variant="primary" size="sm" onClick={openReview} className="shrink-0">
        Review Now
      </Button>
    </div>
  )
}
