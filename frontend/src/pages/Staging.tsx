import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useCategories, useCommitBatch, useDiscardBatch, useStagingBatch, useUpdateStagingRow } from '../api/hooks'
import { categoryColor } from '../lib/categoryColor'
import { fmtDate, fmtSigned } from '../lib/format'
import type { StagingRow } from '../api/types'

const AMBER_BG = 'oklch(20% 0.02 70)'
const AMBER_BADGE_BG = 'oklch(30% 0.07 70)'
const AMBER_BADGE_FG = 'oklch(82% 0.13 70)'

function StagingRowPopover({
  row,
  batchId,
  onApplied,
}: {
  row: StagingRow
  batchId: string
  onApplied: () => void
}) {
  const categoriesQ = useCategories()
  const updateRow = useUpdateStagingRow(batchId)
  const [category, setCategory] = useState(row.category)
  const [saveAsRule, setSaveAsRule] = useState(false)
  const [saveAsContact, setSaveAsContact] = useState(false)

  return (
    <div
      className="px-5 py-4 flex items-end gap-3 border-b border-border"
      style={{ background: AMBER_BG }}
    >
      <div className="flex-1">
        <div className="text-[11px] text-muted mb-1">Assign category</div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-full text-[13px] px-2.5 py-1.5 rounded-md border border-border bg-input text-text"
        >
          {(categoriesQ.data ?? []).map((c) => (
            <option key={c.id} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <label className="flex items-center gap-1.5 text-[12px] text-text pb-2 cursor-pointer">
        <input type="checkbox" checked={saveAsRule} onChange={(e) => setSaveAsRule(e.target.checked)} />
        Save as rule
      </label>
      <label className="flex items-center gap-1.5 text-[12px] text-text pb-2 cursor-pointer">
        <input type="checkbox" checked={saveAsContact} onChange={(e) => setSaveAsContact(e.target.checked)} />
        Save as contact mapping
      </label>
      <button
        onClick={() =>
          updateRow.mutate(
            {
              index: row.index,
              body: { category, save_as_rule: saveAsRule, save_as_contact: saveAsContact },
            },
            { onSuccess: onApplied },
          )
        }
        disabled={updateRow.isPending}
        className="text-[12px] font-semibold px-3.5 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
      >
        Apply
      </button>
    </div>
  )
}

export function Staging() {
  const { batchId } = useParams<{ batchId: string }>()
  const navigate = useNavigate()
  const batchQ = useStagingBatch(batchId)
  const categoriesQ = useCategories()
  const commit = useCommitBatch()
  const discard = useDiscardBatch()
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  if (!batchId) {
    return (
      <div className="p-9 text-center text-muted">
        No statement is currently staged.{' '}
        <Link to="/" className="text-accent hover:text-accent-hover">
          Upload one to get started.
        </Link>
      </div>
    )
  }

  if (batchQ.isLoading) return <div className="p-9 text-muted">Loading staged transactions…</div>
  if (batchQ.isError || !batchQ.data) {
    return (
      <div className="p-9 text-center text-muted">
        This staging batch is no longer available.{' '}
        <Link to="/" className="text-accent hover:text-accent-hover">
          Upload a statement.
        </Link>
      </div>
    )
  }

  const batch = batchQ.data
  const visibleRows = batch.rows.filter((r) => !r.is_duplicate)

  async function handleCommit() {
    await commit.mutateAsync(batchId!)
    navigate('/dashboard')
  }

  async function handleDiscard() {
    await discard.mutateAsync(batchId!)
    navigate('/')
  }

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="text-[22px] font-bold mb-0.5">Staging &amp; Pre-Commit Review</div>
      <div className="text-[13px] text-muted mb-5">
        {batch.source_filename} — parsed, awaiting commit
      </div>

      <div className="flex gap-3 mb-5 flex-wrap">
        <div className="bg-card border border-border rounded-[10px] px-4.5 py-3">
          <div className="text-[11px] text-muted-2">New Extracted</div>
          <div className="text-xl font-bold font-mono">{batch.new_extracted}</div>
        </div>
        <div className="bg-card border border-border rounded-[10px] px-4.5 py-3">
          <div className="text-[11px] text-muted-2">Duplicates Skipped</div>
          <div className="text-xl font-bold font-mono text-muted-2">{batch.duplicates_skipped}</div>
        </div>
        <div className="bg-card border border-border rounded-[10px] px-4.5 py-3">
          <div className="text-[11px] text-muted-2">New Accounts Provisioned</div>
          <div className="text-xl font-bold font-mono">{batch.new_accounts_provisioned}</div>
        </div>
        {batch.needs_category_count > 0 && (
          <div className="rounded-[10px] px-4.5 py-3" style={{ background: 'oklch(24% 0.05 70)', border: '1px solid oklch(40% 0.08 70)' }}>
            <div className="text-[11px]" style={{ color: 'oklch(80% 0.12 70)' }}>
              Needs Category (Others &gt; PayNow)
            </div>
            <div className="text-xl font-bold font-mono" style={{ color: 'oklch(85% 0.12 70)' }}>
              {batch.needs_category_count}
            </div>
          </div>
        )}
      </div>

      <div className="bg-card border border-border rounded-xl overflow-hidden mb-5">
        <div className="grid grid-cols-[80px_1fr_180px_110px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-border/70">
          <div>Date</div>
          <div>Description</div>
          <div>Category</div>
          <div className="text-right">Amount</div>
        </div>
        {visibleRows.map((row) => {
          const isOpen = openIndex === row.index
          const cc = row.needs_review
            ? { bg: AMBER_BADGE_BG, fg: AMBER_BADGE_FG }
            : categoryColor(categoriesQ.data, row.category)
          return (
            <div key={row.index}>
              <div
                onClick={() => row.needs_review && setOpenIndex(isOpen ? null : row.index)}
                className={`grid grid-cols-[80px_1fr_180px_110px] items-center px-5 py-3 text-[13px] border-b border-border/70 ${
                  row.needs_review ? 'cursor-pointer' : ''
                }`}
                style={{ background: row.needs_review ? AMBER_BG : isOpen ? '#22232c' : undefined }}
              >
                <div className="text-muted font-mono text-xs">{fmtDate(row.transaction_date)}</div>
                <div className="truncate pr-2">{row.raw_description}</div>
                <div>
                  <span
                    className="text-[11px] px-2 py-0.5 rounded-md"
                    style={{ background: cc.bg, color: cc.fg }}
                  >
                    {row.needs_review ? 'Others > PayNow' : row.category}
                  </span>
                </div>
                <div className={`text-right font-mono ${row.amount > 0 ? 'text-success' : 'text-text'}`}>
                  {fmtSigned(row.amount)}
                </div>
              </div>
              {isOpen && (
                <StagingRowPopover row={row} batchId={batchId} onApplied={() => setOpenIndex(null)} />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex justify-end gap-3 sticky bottom-5">
        <button
          onClick={handleDiscard}
          disabled={discard.isPending}
          className="text-[13px] font-semibold px-4.5 py-2.5 rounded-lg cursor-pointer bg-card disabled:opacity-60"
          style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
        >
          Discard Batch
        </button>
        <button
          onClick={handleCommit}
          disabled={commit.isPending || visibleRows.length === 0}
          className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Commit {batch.new_extracted} Transaction{batch.new_extracted === 1 ? '' : 's'}
        </button>
      </div>
    </div>
  )
}
