import { useState } from 'react'
import { useCategories } from '../api/hooks'
import type { Contact } from '../api/types'
import { CONTACT_IDENTIFIER_HINT } from '../lib/localization'
import { Button } from './Button'
import { categoryOptionElements } from './CategoryOptions'
import { Field, Input } from './Field'
import { Modal } from './Modal'
import { Select } from './Select'

export interface ContactFormSubmitValues {
  name: string
  default_category: string
  identifiers: string[]
}

// Originally Contacts.tsx-only (create/edit a contact from the Contacts
// page). Pulled out into its own file so the pre-commit review dialog's
// "Save as Contact" action (ReviewDialog.tsx) can open this exact same
// form instead of a one-click checkbox that silently guessed an identifier
// from the raw description - one visual design for "map an identifier to a
// person" instead of a real dialog and a shortcut that drift apart.
//
// The two callers still submit differently underneath (Contacts.tsx
// creates/updates a contact directly; a review dialog also needs to apply
// this transaction's own category/label alongside the contact save, via
// the batch row-update endpoint) - `onSubmit` is how that stays the
// caller's problem rather than this component's, mirroring
// RuleFormModal's onSubmit split.
export function ContactFormModal({
  contact,
  initialName,
  initialCategory,
  onSubmit,
  saving = false,
  onClose,
}: {
  contact?: Contact
  initialName?: string
  initialCategory?: string
  onSubmit: (body: ContactFormSubmitValues) => Promise<void>
  saving?: boolean
  onClose: () => void
}) {
  const categoriesQ = useCategories()
  const [name, setName] = useState(contact?.name ?? initialName ?? '')
  const [category, setCategory] = useState(contact?.default_category ?? initialCategory ?? '')
  const [identifiers, setIdentifiers] = useState<string[]>(contact?.identifiers.length ? contact.identifiers : [''])

  const isEditing = contact != null

  function updateIdentifier(i: number, value: string) {
    setIdentifiers((prev) => prev.map((id, idx) => (idx === i ? value : id)))
  }

  async function handleSave() {
    if (!name.trim()) return
    await onSubmit({
      name: name.trim(),
      default_category: category || categoriesQ.data?.[0]?.name || '',
      identifiers: identifiers.map((i) => i.trim()).filter(Boolean),
    })
    onClose()
  }

  return (
    <Modal onClose={onClose} title={isEditing ? 'Edit Contact' : 'Add Contact'}>
      <Field label="Name" className="mb-3.5">
        <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Auntie Mei" />
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
