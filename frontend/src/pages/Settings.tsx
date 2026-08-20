import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRelocateDb, useResetDb, useSettings } from '../api/hooks'
import { Modal } from '../components/Modal'
import { fmtBytes } from '../lib/format'

function RelocateModal({ dbSize, onClose }: { dbSize: string; onClose: () => void }) {
  const relocate = useRelocateDb()
  const [newPath, setNewPath] = useState('')

  async function handleMigrate() {
    if (!newPath.trim()) return
    await relocate.mutateAsync(newPath.trim())
    onClose()
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5">Change Database Path</div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        This migrates a <strong className="text-text">{dbSize}</strong> database file to the new location. Active
        connections will be closed during the move, then reopened at the new path.
      </div>
      <div className="text-xs text-muted mb-1">New location</div>
      <input
        value={newPath}
        onChange={(e) => setNewPath(e.target.value)}
        placeholder="/Users/you/Documents/sg-tracker-data.db"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      {relocate.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not relocate the database. Check the path.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleMigrate}
          disabled={relocate.isPending || !newPath.trim()}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Migrate Database
        </button>
      </div>
    </Modal>
  )
}

function NuclearResetModal({ onClose }: { onClose: () => void }) {
  const reset = useResetDb()
  const navigate = useNavigate()
  const [confirm, setConfirm] = useState('')
  const canReset = confirm === 'DELETE'

  async function handleReset() {
    if (!canReset) return
    await reset.mutateAsync(confirm)
    onClose()
    navigate('/')
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5" style={{ color: 'oklch(72% 0.16 25)' }}>
        Nuclear Reset
      </div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        This permanently deletes all accounts, transactions, contacts and rules. Type{' '}
        <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <input
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder="DELETE"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleReset}
          disabled={!canReset || reset.isPending}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer"
          style={{
            background: canReset ? 'oklch(55% 0.19 25)' : '#2c2d38',
            color: canReset ? '#fff' : 'var(--color-muted-2)',
            cursor: canReset ? 'pointer' : 'not-allowed',
          }}
        >
          Purge Everything
        </button>
      </div>
    </Modal>
  )
}

export function Settings() {
  const settingsQ = useSettings()
  const [relocateOpen, setRelocateOpen] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)

  const dbSize = settingsQ.data ? fmtBytes(settingsQ.data.size_bytes) : '—'

  return (
    <div className="px-9 pt-7 pb-15 max-w-2xl">
      <div className="text-[22px] font-bold mb-5">Settings &amp; Storage</div>

      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <div className="text-[13px] font-semibold mb-3.5">Database</div>
        <div className="text-xs text-muted mb-0.5">Path</div>
        <div className="text-[13px] font-mono mb-3 break-all">{settingsQ.data?.db_path ?? '—'}</div>
        <div className="flex gap-6 mb-4">
          <div>
            <div className="text-xs text-muted">Size</div>
            <div className="text-[13px] font-mono">{dbSize}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Schema version</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.schema_version ?? '—'}</div>
          </div>
        </div>
        <button
          onClick={() => setRelocateOpen(true)}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Change Database Path
        </button>
      </div>

      <div className="bg-card rounded-xl p-5" style={{ border: '1px solid oklch(40% 0.08 25)' }}>
        <div className="text-[13px] font-semibold mb-1.5" style={{ color: 'oklch(72% 0.16 25)' }}>
          Danger Zone
        </div>
        <div className="text-[13px] text-muted mb-3.5 leading-relaxed">
          Nuclear Reset permanently deletes all transactions, rules, contacts and accounts from the local database.
          This cannot be undone.
        </div>
        <button
          onClick={() => setResetOpen(true)}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer text-white"
          style={{ background: 'oklch(55% 0.19 25)' }}
        >
          Nuclear Reset
        </button>
      </div>

      {relocateOpen && <RelocateModal dbSize={dbSize} onClose={() => setRelocateOpen(false)} />}
      {resetOpen && <NuclearResetModal onClose={() => setResetOpen(false)} />}
    </div>
  )
}
