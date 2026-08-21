import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useDeleteAllContacts,
  useDeleteAllRules,
  useDeleteAllTransactions,
  useRelocateDb,
  useResetDb,
  useSettings,
} from '../api/hooks'
import { Modal } from '../components/Modal'
import { fmtBytes } from '../lib/format'
import { ACCENT_PRESETS, DEFAULT_ACCENT, loadStoredAccentColor, resetAccentColor, saveAccentColor } from '../lib/accentColor'

function AppearanceSection() {
  const [accent, setAccent] = useState(loadStoredAccentColor())

  function pick(hex: string) {
    setAccent(hex)
    saveAccentColor(hex)
  }

  function reset() {
    setAccent(DEFAULT_ACCENT)
    resetAccentColor()
  }

  return (
    <div className="bg-card border border-border rounded-xl p-5 mb-4">
      <div className="text-[13px] font-semibold mb-1">Appearance</div>
      <div className="text-xs text-muted mb-3.5">Choose the accent color used for buttons, links, and highlights.</div>
      <div className="flex items-center gap-2.5 flex-wrap">
        {ACCENT_PRESETS.map((p) => (
          <button
            key={p.hex}
            onClick={() => pick(p.hex)}
            title={p.name}
            className="w-7 h-7 rounded-full cursor-pointer"
            style={{
              background: p.hex,
              outline: accent.toLowerCase() === p.hex.toLowerCase() ? '2px solid var(--color-text)' : 'none',
              outlineOffset: 2,
              border: 'none',
            }}
          />
        ))}
        <label
          title="Custom color"
          className="relative w-7 h-7 rounded-full cursor-pointer border border-border overflow-hidden flex items-center justify-center"
          style={{
            background: ACCENT_PRESETS.some((p) => p.hex.toLowerCase() === accent.toLowerCase())
              ? 'conic-gradient(from 0deg, #e35fd0, #a78bfa, #5b9dff, #2dd4bf, #4ade80, #fbbf24, #fb923c, #f87171, #e35fd0)'
              : accent,
          }}
        >
          <input
            type="color"
            value={accent}
            onChange={(e) => pick(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer"
          />
        </label>
        <button
          onClick={reset}
          className="text-[12px] text-muted hover:text-text cursor-pointer border-none bg-transparent ml-1"
        >
          Reset to default
        </button>
      </div>
    </div>
  )
}

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

function ScopedDeleteModal({
  title,
  description,
  confirmLabel,
  mutation,
  onClose,
}: {
  title: string
  description: string
  confirmLabel: string
  mutation: ReturnType<typeof useDeleteAllRules> | ReturnType<typeof useDeleteAllContacts> | ReturnType<typeof useDeleteAllTransactions>
  onClose: () => void
}) {
  const [confirm, setConfirm] = useState('')
  const canDelete = confirm === 'DELETE'

  async function handleDelete() {
    if (!canDelete) return
    try {
      await mutation.mutateAsync(confirm)
      onClose()
    } catch {
      // swallow - mutation.isError below renders the failure, modal stays open so the user can retry
    }
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5" style={{ color: 'oklch(72% 0.16 25)' }}>
        {title}
      </div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        {description} Type <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <input
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder="DELETE"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      {mutation.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not complete the deletion. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleDelete}
          disabled={!canDelete || mutation.isPending}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer"
          style={{
            background: canDelete ? 'var(--color-danger)' : 'var(--color-border)',
            color: canDelete ? 'var(--color-danger-fg)' : 'var(--color-muted-2)',
            cursor: canDelete ? 'pointer' : 'not-allowed',
          }}
        >
          {confirmLabel}
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
    try {
      await reset.mutateAsync(confirm)
      onClose()
      navigate('/')
    } catch {
      // swallow - reset.isError below renders the failure, modal stays open so the user can retry
    }
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
      {reset.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not complete the reset. Please try again.</div>
      )}
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
            background: canReset ? 'var(--color-danger)' : 'var(--color-border)',
            color: canReset ? 'var(--color-danger-fg)' : 'var(--color-muted-2)',
            cursor: canReset ? 'pointer' : 'not-allowed',
          }}
        >
          Purge Everything
        </button>
      </div>
    </Modal>
  )
}

type DeleteScope = 'rules' | 'contacts' | 'transactions' | null

export function Settings() {
  const settingsQ = useSettings()
  const [relocateOpen, setRelocateOpen] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  const [deleteScope, setDeleteScope] = useState<DeleteScope>(null)

  const deleteRules = useDeleteAllRules()
  const deleteContacts = useDeleteAllContacts()
  const deleteTransactions = useDeleteAllTransactions()

  const dbSize = settingsQ.data ? fmtBytes(settingsQ.data.size_bytes) : '—'

  return (
    <div className="px-9 pt-7 pb-15 max-w-2xl">
      <div className="text-[22px] font-bold font-display mb-5">Settings &amp; Storage</div>

      <AppearanceSection />

      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <div className="text-[13px] font-semibold mb-1">Region</div>
        <div className="text-xs text-muted mb-3.5">
          Statement parsing, currency formatting, and the default rule bank are all specific to this region.
        </div>
        <div className="flex gap-6 flex-wrap">
          <div>
            <div className="text-xs text-muted">Country</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.country_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Currency</div>
            <div className="text-[13px] font-mono">
              {settingsQ.data ? `${settingsQ.data.currency_code} (${settingsQ.data.currency_symbol})` : '—'}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Transfer scheme</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.transfer_scheme_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Supported banks</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.supported_banks.join(', ') ?? '—'}</div>
          </div>
        </div>
      </div>

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
          Selectively clear one part of the local database, or permanently delete everything. None of this can be
          undone.
        </div>
        <div className="flex gap-2.5 flex-wrap mb-4">
          <button
            onClick={() => setDeleteScope('rules')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Rules
          </button>
          <button
            onClick={() => setDeleteScope('contacts')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Contacts
          </button>
          <button
            onClick={() => setDeleteScope('transactions')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Transactions
          </button>
        </div>
        <div className="h-px bg-border/70 mb-4" />
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
      {deleteScope === 'rules' && (
        <ScopedDeleteModal
          title="Delete All Rules"
          description="This permanently deletes every rule you've created. Built-in default rules are not affected."
          confirmLabel="Delete Rules"
          mutation={deleteRules}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'contacts' && (
        <ScopedDeleteModal
          title="Delete All Contacts"
          description="This permanently deletes every contact and their linked identifiers."
          confirmLabel="Delete Contacts"
          mutation={deleteContacts}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'transactions' && (
        <ScopedDeleteModal
          title="Delete All Transactions"
          description="This permanently deletes every committed transaction. Accounts themselves are kept, so you can re-upload statements without losing account setup."
          confirmLabel="Delete Transactions"
          mutation={deleteTransactions}
          onClose={() => setDeleteScope(null)}
        />
      )}
    </div>
  )
}
