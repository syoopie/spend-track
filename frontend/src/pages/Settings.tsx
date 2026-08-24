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
import { AiSection } from '../components/AiSection'
import { AppearanceSection } from '../components/AppearanceSection'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Field, Input } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageShell } from '../components/PageShell'
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
      <div className="text-md text-muted leading-relaxed mb-4">
        This migrates a <strong className="text-text">{dbSize}</strong> database file to the new location. Active
        connections will be closed during the move, then reopened at the new path.
      </div>
      <Field label="New location" className="mb-4.5">
        <Input
          mono
          value={newPath}
          onChange={(e) => setNewPath(e.target.value)}
          placeholder="/Users/you/Documents/sg-tracker-data.db"
        />
      </Field>
      {relocate.isError && (
        <div className="text-xs text-danger-text mb-3">Could not relocate the database. Check the path.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={handleMigrate} disabled={relocate.isPending || !newPath.trim()}>
          Migrate Database
        </Button>
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
      <div className="text-base font-bold mb-2.5 text-danger-text">{title}</div>
      <div className="text-md text-muted leading-relaxed mb-4">
        {description} Type <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <Input mono value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="DELETE" className="mb-4.5" />
      {mutation.isError && (
        <div className="text-xs text-danger-text mb-3">Could not complete the deletion. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" onClick={handleDelete} disabled={!canDelete || mutation.isPending}>
          {confirmLabel}
        </Button>
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
      <div className="text-base font-bold mb-2.5 text-danger-text">Nuclear Reset</div>
      <div className="text-md text-muted leading-relaxed mb-4">
        This permanently deletes all accounts, transactions, contacts and rules. Type{' '}
        <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <Input mono value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="DELETE" className="mb-4.5" />
      {reset.isError && (
        <div className="text-xs text-danger-text mb-3">Could not complete the reset. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" onClick={handleReset} disabled={!canReset || reset.isPending}>
          Purge Everything
        </Button>
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
    <PageShell title="Settings & Storage" maxWidth="max-w-2xl">
      <AppearanceSection />

      <AiSection settings={settingsQ.data} />

      <Card className="mb-4">
        <div className="text-md font-semibold mb-1">Region</div>
        <div className="text-xs text-muted mb-3.5">
          Statement parsing, currency formatting, and the default rule bank are all specific to this region.
        </div>
        <div className="flex gap-6 flex-wrap">
          <div>
            <div className="text-xs text-muted">Country</div>
            <div className="text-md font-mono">{settingsQ.data?.country_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Currency</div>
            <div className="text-md font-mono">
              {settingsQ.data ? `${settingsQ.data.currency_code} (${settingsQ.data.currency_symbol})` : '—'}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Transfer scheme</div>
            <div className="text-md font-mono">{settingsQ.data?.transfer_scheme_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Supported banks</div>
            <div className="text-md font-mono">{settingsQ.data?.supported_banks.join(', ') ?? '—'}</div>
          </div>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="text-md font-semibold mb-3.5">Database</div>
        <div className="text-xs text-muted mb-0.5">Path</div>
        <div className="text-md font-mono mb-3 break-all">{settingsQ.data?.db_path ?? '—'}</div>
        <div className="flex gap-6 mb-4">
          <div>
            <div className="text-xs text-muted">Size</div>
            <div className="text-md font-mono">{dbSize}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Schema version</div>
            <div className="text-md font-mono">{settingsQ.data?.schema_version ?? '—'}</div>
          </div>
        </div>
        <Button variant="secondary" className="font-semibold" onClick={() => setRelocateOpen(true)}>
          Change Database Path
        </Button>
      </Card>

      <Card style={{ border: '1px solid var(--color-danger-surface-border)' }}>
        <div className="text-md font-semibold mb-1.5 text-danger-text">Danger Zone</div>
        <div className="text-md text-muted mb-3.5 leading-relaxed">
          Selectively clear one part of the local database, or permanently delete everything. None of this can be
          undone.
        </div>
        <div className="flex gap-2.5 flex-wrap mb-4">
          <Button variant="danger-outline" onClick={() => setDeleteScope('rules')}>
            Delete All Rules
          </Button>
          <Button variant="danger-outline" onClick={() => setDeleteScope('contacts')}>
            Delete All Contacts
          </Button>
          <Button variant="danger-outline" onClick={() => setDeleteScope('transactions')}>
            Delete All Transactions
          </Button>
        </div>
        <div className="h-px bg-border/70 mb-4" />
        <Button variant="danger" onClick={() => setResetOpen(true)}>
          Nuclear Reset
        </Button>
      </Card>

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
    </PageShell>
  )
}
