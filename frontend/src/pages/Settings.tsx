import { Download, FileX2, Loader2, Settings as SettingsIcon, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useCheckPath,
  useContacts,
  useDeleteAllContacts,
  useDeleteAllRules,
  useDeleteAllTransactions,
  useDeleteTransactionsByFile,
  useRelocateDb,
  useResetDb,
  useRules,
  useSettings,
  useSourceFiles,
  useTransactions,
} from '../api/hooks'
import { AiSection } from '../components/AiSection'
import { AppearanceSection } from '../components/AppearanceSection'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Field, Input } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageShell } from '../components/PageShell'
import { fmtBytes } from '../lib/format'

function RelocateModal({ dbSize, currentPath, onClose }: { dbSize: string; currentPath: string; onClose: () => void }) {
  const relocate = useRelocateDb()
  const checkPath = useCheckPath()
  const [newPath, setNewPath] = useState(currentPath)
  // The result in checkPath.data only describes THIS path - tracked
  // separately so an edit after a check doesn't keep showing the previous
  // (now stale) result as if it still applied to what's on screen.
  const [checkedPath, setCheckedPath] = useState<string | null>(null)

  function handleBlur() {
    const trimmed = newPath.trim()
    if (!trimmed || trimmed === checkedPath) return
    setCheckedPath(trimmed)
    checkPath.mutate(trimmed)
  }

  const pathChanged = newPath.trim() !== currentPath
  const canMigrate = pathChanged && checkedPath === newPath.trim() && checkPath.data?.valid === true

  async function handleMigrate() {
    if (!canMigrate) return
    await relocate.mutateAsync(newPath.trim())
    onClose()
  }

  return (
    <Modal onClose={onClose} width={440} title="Change Database Path">
      <div className="text-md text-muted leading-relaxed mb-4">
        This migrates a <strong className="text-text">{dbSize}</strong> database file to the new location. Active
        connections will be closed during the move, then reopened at the new path.
      </div>
      <Field label="New location" className="mb-1.5">
        <Input
          mono
          value={newPath}
          onChange={(e) => {
            setNewPath(e.target.value)
            setCheckedPath(null)
          }}
          onBlur={handleBlur}
          placeholder="/Users/you/Documents/sg-tracker-data.db"
        />
      </Field>
      {/* SET-6: validated on blur, not left to fail silently until Migrate
          is clicked - shows the resolved absolute path and free space at
          the target directory before the button is even enabled. */}
      <div className="mb-4.5 min-h-5">
        {checkPath.isPending ? (
          <div className="text-2xs text-muted flex items-center gap-1.5">
            <Loader2 size={12} className="animate-spin" /> Checking…
          </div>
        ) : checkPath.data && checkedPath === newPath.trim() ? (
          checkPath.data.valid ? (
            <div className="text-2xs text-success font-mono break-all">
              {checkPath.data.resolved_path}
              {checkPath.data.free_bytes != null && ` · ${fmtBytes(checkPath.data.free_bytes)} free`}
            </div>
          ) : (
            <div className="text-2xs text-danger-text">{checkPath.data.error}</div>
          )
        ) : !pathChanged ? (
          <div className="text-2xs text-muted-2">Current location.</div>
        ) : null}
      </div>
      {relocate.isError && (
        <div className="text-xs text-danger-text mb-3">Could not relocate the database. Check the path.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={handleMigrate} disabled={relocate.isPending || !canMigrate}>
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
    <Modal onClose={onClose} width={420} title={<span className="text-danger-text">{title}</span>}>
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

// A single confirm button, no type-DELETE step (SET-3) - reserved for the
// two scoped deletes that are recoverable by re-doing normal, everyday work
// (re-upload a statement to regenerate rules via the review dialog, re-add a
// contact). Delete All Transactions and Nuclear Reset keep the type-DELETE
// step in ScopedDeleteModal/NuclearResetModal below - those two destroy
// data with no equivalent "just redo it" path.
function SimpleConfirmModal({
  title,
  description,
  confirmLabel,
  mutation,
  onClose,
}: {
  title: string
  description: string
  confirmLabel: string
  mutation: ReturnType<typeof useDeleteAllRules> | ReturnType<typeof useDeleteAllContacts>
  onClose: () => void
}) {
  async function handleConfirm() {
    try {
      await mutation.mutateAsync('DELETE')
      onClose()
    } catch {
      // swallow - mutation.isError below renders the failure, modal stays open so the user can retry
    }
  }

  return (
    <Modal onClose={onClose} width={400} title={<span className="text-danger-text">{title}</span>}>
      <div className="text-md text-muted leading-relaxed mb-4.5">{description}</div>
      {mutation.isError && (
        <div className="text-xs text-danger-text mb-3">Could not complete the deletion. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" onClick={handleConfirm} disabled={mutation.isPending}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}

// Single-confirm, no typed-DELETE step - same reasoning as
// SimpleConfirmModal above: undoing this is a normal, everyday action
// (re-upload the exact same PDF), not a reason to make it as hard to
// trigger as Delete All Transactions or Nuclear Reset.
function DeleteFileModal({
  filename,
  count,
  onClose,
}: {
  filename: string
  count: number
  onClose: () => void
}) {
  const deleteByFile = useDeleteTransactionsByFile()

  async function handleConfirm() {
    try {
      await deleteByFile.mutateAsync(filename)
      onClose()
    } catch {
      // swallow - deleteByFile.isError below renders the failure, modal stays open so the user can retry
    }
  }

  return (
    <Modal onClose={onClose} width={440} title={<span className="text-danger-text">Delete Uploaded File</span>}>
      <div className="text-md text-muted leading-relaxed mb-4.5">
        This permanently deletes the {count} transaction{count === 1 ? '' : 's'} committed from{' '}
        <strong className="font-mono text-text break-all">{filename}</strong>. Re-upload the same PDF to bring them
        back.
      </div>
      {deleteByFile.isError && (
        <div className="text-xs text-danger-text mb-3">Could not complete the deletion. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="danger" onClick={handleConfirm} disabled={deleteByFile.isPending}>
          Delete Transactions
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
    <Modal onClose={onClose} width={420} title={<span className="text-danger-text">Nuclear Reset</span>}>
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
  const [deleteFileTarget, setDeleteFileTarget] = useState<{ filename: string; count: number } | null>(null)

  const deleteRules = useDeleteAllRules()
  const deleteContacts = useDeleteAllContacts()
  const deleteTransactions = useDeleteAllTransactions()
  const sourceFilesQ = useSourceFiles()

  // Live counts for the Danger Zone (SET-3) - "This deletes 23 rules" beats
  // an undifferentiated "This permanently deletes every rule" regardless of
  // whether that's 2 rules or 200. Only fetched for the count itself, so
  // there's no attempt to reuse/paginate these the way Rules/Contacts/
  // Dashboard's own list views do.
  const rulesQ = useRules(false)
  const contactsQ = useContacts()
  const txQ = useTransactions({ include_excluded: true })
  const rulesCount = rulesQ.data?.length ?? 0
  const contactsCount = contactsQ.data?.length ?? 0
  const txCount = txQ.data?.length ?? 0

  const dbSize = settingsQ.data ? fmtBytes(settingsQ.data.size_bytes) : '—'

  return (
    <PageShell title="Settings & Storage" icon={SettingsIcon} maxWidth="max-w-4xl">
      <AppearanceSection />

      <AiSection settings={settingsQ.data} />

      <Card className="mb-4">
        <div className="text-md font-semibold font-display mb-1">Region</div>
        <div className="text-xs text-muted mb-3.5">
          Statement parsing, currency formatting, and the default rule bank are all specific to this region.
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
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
            {/* Split deliberately: a bank whose statements are recognized but
                not yet parsed used to be listed here as "supported", which is
                the opposite of what an upload does with it. Both lists come
                from the parser registry, so a new parser moves a name across
                on its own. */}
            <div className="text-xs text-muted">Statements supported</div>
            <div className="text-md font-mono">{settingsQ.data?.supported_banks.join(', ') || '—'}</div>
            {(settingsQ.data?.detected_banks.length ?? 0) > 0 && (
              <div className="text-2xs text-muted-2 mt-1">
                {settingsQ.data?.detected_banks.join(', ')} recognized, parser not built yet
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card className="mb-4">
        <div className="text-md font-semibold font-display mb-3.5">Database</div>
        <div className="text-xs text-muted mb-0.5">Path</div>
        <div className="text-md font-mono mb-3 break-all">{settingsQ.data?.db_path ?? '—'}</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-xs text-muted">Size</div>
            <div className="text-md font-mono">{dbSize}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Schema version</div>
            <div className="text-md font-mono">{settingsQ.data?.schema_version ?? '—'}</div>
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* A plain anchor, not a Button with an onClick: the browser's own
              download handling is what puts the file in Downloads and shows
              the progress. Fetching it into JS to trigger a save would buy
              nothing and break the "just works" case. */}
          <a
            href="/api/data-lifecycle/export"
            download
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg border border-border bg-input text-text text-md font-semibold no-underline
              transition-colors hover:border-accent cursor-pointer
              focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
          >
            <Download size={14} />
            Download Backup
          </a>
          <Button variant="secondary" className="font-semibold" onClick={() => setRelocateOpen(true)}>
            Change Database Path
          </Button>
        </div>
        <div className="text-xs text-muted mt-2.5 leading-relaxed">
          A zip holding your database, your settings and a note explaining how to put them back — enough to restore
          on this computer or move to another one. AI provider keys are left out on purpose; re-enter yours after
          restoring.
        </div>
      </Card>

      {(sourceFilesQ.data?.length ?? 0) > 0 && (
        <Card className="mb-4">
          <div className="text-md font-semibold font-display mb-1">Uploaded Files</div>
          <div className="text-xs text-muted mb-3.5">
            Every PDF that has committed transactions. Delete one to undo a bad upload — re-uploading the same file
            brings its transactions back.
          </div>
          <div className="flex flex-col gap-2">
            {(sourceFilesQ.data ?? []).map((f) => (
              <div
                key={f.filename}
                className="flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-lg border border-border bg-input"
              >
                <div className="min-w-0 flex items-center gap-2">
                  <FileX2 size={14} className="text-muted-2 shrink-0" />
                  <span className="text-md font-mono truncate" title={f.filename}>
                    {f.filename}
                  </span>
                  <span className="text-xs text-muted-2 shrink-0">
                    · {f.transaction_count} transaction{f.transaction_count === 1 ? '' : 's'}
                  </span>
                </div>
                <button
                  onClick={() => setDeleteFileTarget({ filename: f.filename, count: f.transaction_count })}
                  title={`Delete transactions from ${f.filename}`}
                  className="shrink-0 border-none bg-transparent cursor-pointer text-muted-2 hover:text-danger-text p-1"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card style={{ border: '1px solid var(--color-danger-surface-border)' }}>
        <div className="text-md font-semibold font-display mb-1.5 text-danger-text">Danger Zone</div>
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

      {relocateOpen && (
        <RelocateModal dbSize={dbSize} currentPath={settingsQ.data?.db_path ?? ''} onClose={() => setRelocateOpen(false)} />
      )}
      {resetOpen && <NuclearResetModal onClose={() => setResetOpen(false)} />}
      {deleteFileTarget && (
        <DeleteFileModal
          filename={deleteFileTarget.filename}
          count={deleteFileTarget.count}
          onClose={() => setDeleteFileTarget(null)}
        />
      )}
      {deleteScope === 'rules' && (
        <SimpleConfirmModal
          title="Delete All Rules"
          description={`This permanently deletes ${rulesCount} rule${rulesCount === 1 ? '' : 's'} you've created. Built-in default rules are not affected.`}
          confirmLabel="Delete Rules"
          mutation={deleteRules}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'contacts' && (
        <SimpleConfirmModal
          title="Delete All Contacts"
          description={`This permanently deletes ${contactsCount} contact${contactsCount === 1 ? '' : 's'} and their linked identifiers.`}
          confirmLabel="Delete Contacts"
          mutation={deleteContacts}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'transactions' && (
        <ScopedDeleteModal
          title="Delete All Transactions"
          description={`This permanently deletes ${txCount} committed transaction${txCount === 1 ? '' : 's'}. Accounts themselves are kept, so you can re-upload statements without losing account setup.`}
          confirmLabel="Delete Transactions"
          mutation={deleteTransactions}
          onClose={() => setDeleteScope(null)}
        />
      )}
    </PageShell>
  )
}
