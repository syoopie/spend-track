import { useRef, useState } from 'react'
import {
  useCategories,
  useContacts,
  useCreateContact,
  useImportContactsCsv,
} from '../api/hooks'
import { CategoryBadge } from '../components/CategoryBadge'
import { Modal } from '../components/Modal'
import { Select } from '../components/Select'
import { categoryIcon } from '../lib/categoryColor'
import { fmtPlain } from '../lib/format'

function AddContactModal({ onClose }: { onClose: () => void }) {
  const categoriesQ = useCategories()
  const createContact = useCreateContact()
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [identifiers, setIdentifiers] = useState<string[]>([''])

  function updateIdentifier(i: number, value: string) {
    setIdentifiers((prev) => prev.map((id, idx) => (idx === i ? value : id)))
  }

  async function handleSave() {
    if (!name.trim()) return
    await createContact.mutateAsync({
      name: name.trim(),
      default_category: category || categoriesQ.data?.[0]?.name || '',
      identifiers: identifiers.map((i) => i.trim()).filter(Boolean),
    })
    onClose()
  }

  return (
    <Modal onClose={onClose}>
      <div className="text-base font-bold mb-4">Add Contact</div>

      <div className="text-xs text-muted mb-1">Name</div>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. Auntie Mei"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] mb-3.5"
      />

      <div className="text-xs text-muted mb-1">Default Category</div>
      <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-full mb-3.5">
        <option value="">Select category…</option>
        {(categoriesQ.data ?? []).map((c) => {
          const Icon = categoryIcon(categoriesQ.data, c.name)
          return (
            <option key={c.id} value={c.name}>
              <Icon size={12} className="shrink-0" /> {c.name}
            </option>
          )
        })}
      </Select>

      <div className="text-xs text-muted mb-1.5">Linked Identifiers</div>
      {identifiers.map((identifier, i) => (
        <div key={i} className="flex gap-2 mb-2">
          <input
            value={identifier}
            onChange={(e) => updateIdentifier(i, e.target.value)}
            placeholder="+65 9xxx xxxx, UEN, or account no."
            className="flex-1 box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px]"
          />
        </div>
      ))}
      <button
        onClick={() => setIdentifiers((prev) => [...prev, ''])}
        className="text-xs text-accent bg-transparent border-none cursor-pointer p-0 mb-4.5"
      >
        + Add another identifier
      </button>

      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={createContact.isPending || !name.trim()}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Save Contact
        </button>
      </div>
    </Modal>
  )
}

export function Contacts() {
  const contactsQ = useContacts()
  const categoriesQ = useCategories()
  const importCsv = useImportContactsCsv()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [importResult, setImportResult] = useState<string | null>(null)

  async function handleImport(file: File) {
    const result = await importCsv.mutateAsync(file)
    setImportResult(`Imported ${result.contacts_created} new contact(s), updated ${result.contacts_updated}.`)
  }

  return (
    <div className="px-9 pt-7 pb-15">
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <div className="text-[22px] font-bold font-display">Contacts &amp; PayNow Directory</div>
          <div className="text-[13px] text-muted mt-0.5">
            Map phone numbers and UENs to people, so transfers categorize themselves
          </div>
        </div>
        <div className="flex gap-2.5">
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
          <button
            onClick={() => fileInputRef.current?.click()}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border border-border bg-card text-text cursor-pointer"
          >
            Import CSV
          </button>
          <button
            onClick={() => setModalOpen(true)}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer"
          >
            + Add Contact
          </button>
        </div>
      </div>

      {importResult && (
        <div className="text-[13px] text-muted mb-4 bg-card border border-border rounded-lg px-4 py-2.5">
          {importResult}
        </div>
      )}

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="grid grid-cols-[1fr_1.6fr_160px_140px] px-5 py-2.5 text-[11px] text-muted-2 uppercase tracking-wide border-b border-divider">
          <div>Contact</div>
          <div>Linked Identifiers</div>
          <div>Default Category</div>
          <div className="text-right">Historical Spend</div>
        </div>
        {contactsQ.isLoading && <div className="p-5 text-muted text-sm">Loading…</div>}
        {!contactsQ.isLoading && (contactsQ.data ?? []).length === 0 && (
          <div className="p-5 text-muted text-sm">No contacts yet.</div>
        )}
        {(contactsQ.data ?? []).map((c) => (
          <div
            key={c.id}
            className="grid grid-cols-[1fr_1.6fr_160px_140px] items-center px-5 py-3.5 text-[13px] border-b border-divider"
          >
            <div className="font-semibold">{c.name}</div>
            <div className="flex gap-1.5 flex-wrap">
              {c.identifiers.map((id) => (
                <span
                  key={id}
                  className="text-[11px] font-mono px-2 py-0.5 rounded-md bg-input text-text-2"
                >
                  {id}
                </span>
              ))}
            </div>
            <div>
              <CategoryBadge category={c.default_category} categories={categoriesQ.data} />
            </div>
            <div className="text-right font-mono">{fmtPlain(c.historical_spend)}</div>
          </div>
        ))}
      </div>

      {modalOpen && <AddContactModal onClose={() => setModalOpen(false)} />}
    </div>
  )
}
