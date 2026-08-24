import { Pencil } from 'lucide-react'
import { useRef, useState } from 'react'
import {
  useCategories,
  useContacts,
  useCreateContact,
  useImportContactsCsv,
  useUpdateContact,
} from '../api/hooks'
import type { Contact } from '../api/types'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { CategoryBadge } from '../components/CategoryBadge'
import { categoryOptionElements } from '../components/CategoryOptions'
import { Field, Input } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageShell } from '../components/PageShell'
import { Select } from '../components/Select'
import { fmtPlain } from '../lib/format'
import { CONTACT_IDENTIFIER_HINT } from '../lib/localization'

// contact === undefined -> "Add Contact"; contact set -> "Edit Contact",
// pre-filled and saving via PATCH instead of POST.
function ContactFormModal({ contact, onClose }: { contact?: Contact; onClose: () => void }) {
  const categoriesQ = useCategories()
  const createContact = useCreateContact()
  const updateContact = useUpdateContact()
  const [name, setName] = useState(contact?.name ?? '')
  const [category, setCategory] = useState(contact?.default_category ?? '')
  const [identifiers, setIdentifiers] = useState<string[]>(contact?.identifiers.length ? contact.identifiers : [''])

  const isEditing = contact != null
  const saving = createContact.isPending || updateContact.isPending

  function updateIdentifier(i: number, value: string) {
    setIdentifiers((prev) => prev.map((id, idx) => (idx === i ? value : id)))
  }

  async function handleSave() {
    if (!name.trim()) return
    const body = {
      name: name.trim(),
      default_category: category || categoriesQ.data?.[0]?.name || '',
      identifiers: identifiers.map((i) => i.trim()).filter(Boolean),
    }
    if (isEditing) {
      await updateContact.mutateAsync({ id: contact.id, body })
    } else {
      await createContact.mutateAsync(body)
    }
    onClose()
  }

  return (
    <Modal onClose={onClose}>
      <div className="text-base font-bold mb-4">{isEditing ? 'Edit Contact' : 'Add Contact'}</div>

      <Field label="Name" className="mb-3.5">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Auntie Mei" />
      </Field>

      <div className="text-xs text-muted mb-1">Default Category</div>
      <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full mb-3.5">
        <option value="">Select category…</option>
        {categoryOptionElements(categoriesQ.data)}
      </Select>

      <div className="text-xs text-muted mb-1.5">Linked Identifiers</div>
      {identifiers.map((identifier, i) => (
        <div key={i} className="flex gap-2 mb-2">
          <Input value={identifier} onChange={(e) => updateIdentifier(i, e.target.value)} placeholder={CONTACT_IDENTIFIER_HINT} />
        </div>
      ))}
      <button
        onClick={() => setIdentifiers((prev) => [...prev, ''])}
        className="text-xs text-accent bg-transparent border-none cursor-pointer p-0 mb-4.5"
      >
        + Add another identifier
      </button>

      <div className="flex justify-end gap-2.5">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" onClick={handleSave} disabled={saving || !name.trim()}>
          {isEditing ? 'Save Changes' : 'Save Contact'}
        </Button>
      </div>
    </Modal>
  )
}

export function Contacts() {
  const contactsQ = useContacts()
  const categoriesQ = useCategories()
  const importCsv = useImportContactsCsv()
  const fileInputRef = useRef<HTMLInputElement>(null)
  // 'new' opens the modal in Add mode; a Contact opens it pre-filled in Edit mode.
  const [formTarget, setFormTarget] = useState<Contact | 'new' | null>(null)
  const [importResult, setImportResult] = useState<string | null>(null)

  async function handleImport(file: File) {
    const result = await importCsv.mutateAsync(file)
    setImportResult(`Imported ${result.contacts_created} new contact(s), updated ${result.contacts_updated}.`)
  }

  return (
    <PageShell
      title="Contacts & PayNow Directory"
      subtitle="Map phone numbers and UENs to people, so transfers categorize themselves"
      actions={
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleImport(file)
              e.target.value = ''
            }}
          />
          <Button variant="secondary" className="font-semibold" onClick={() => fileInputRef.current?.click()}>
            Import CSV
          </Button>
          <Button variant="primary" onClick={() => setFormTarget('new')}>
            + Add Contact
          </Button>
        </>
      }
    >
      {importResult && (
        <div className="text-md text-muted mb-4 bg-card border border-border rounded-lg px-4 py-2.5">
          {importResult}
        </div>
      )}

      <Card padding="" className="overflow-hidden">
        <div className="grid grid-cols-[1fr_1.6fr_160px_140px_36px] px-5 py-2.5 text-2xs text-muted-2 uppercase tracking-wide border-b border-divider">
          <div>Contact</div>
          <div>Linked Identifiers</div>
          <div>Default Category</div>
          <div className="text-right">Historical Spend</div>
          <div />
        </div>
        {contactsQ.isLoading && <div className="p-5 text-muted text-sm">Loading…</div>}
        {!contactsQ.isLoading && (contactsQ.data ?? []).length === 0 && (
          <div className="p-5 text-muted text-sm">No contacts yet.</div>
        )}
        {(contactsQ.data ?? []).map((c) => (
          <div
            key={c.id}
            className="grid grid-cols-[1fr_1.6fr_160px_140px_36px] items-center px-5 py-3.5 text-md border-b border-divider"
          >
            <div className="font-semibold">{c.name}</div>
            <div className="flex gap-1.5 flex-wrap">
              {c.identifiers.map((id) => (
                <span
                  key={id}
                  className="text-2xs font-mono px-2 py-0.5 rounded-md bg-input text-text-2"
                >
                  {id}
                </span>
              ))}
            </div>
            <div>
              <CategoryBadge category={c.default_category} categories={categoriesQ.data} />
            </div>
            <div className="text-right font-mono">{fmtPlain(c.historical_spend)}</div>
            <div className="text-right">
              <button
                onClick={() => setFormTarget(c)}
                title="Edit contact"
                className="text-muted hover:text-text bg-transparent border-none cursor-pointer p-1 rounded-md"
              >
                <Pencil size={14} />
              </button>
            </div>
          </div>
        ))}
      </Card>

      {formTarget && (
        <ContactFormModal contact={formTarget === 'new' ? undefined : formTarget} onClose={() => setFormTarget(null)} />
      )}
    </PageShell>
  )
}
