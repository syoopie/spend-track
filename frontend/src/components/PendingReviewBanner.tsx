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
      style={{ background: 'oklch(24% 0.05 70)', borderColor: 'oklch(40% 0.08 70)' }}
    >
      <div className="text-[13px]" style={{ color: 'oklch(85% 0.12 70)' }}>
        A statement is awaiting review before it can be committed.
      </div>
      <button
        onClick={openReview}
        className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer shrink-0"
      >
        Review Now
      </button>
    </div>
  )
}
