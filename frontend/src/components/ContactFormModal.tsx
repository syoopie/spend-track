import { useState } from 'react'
import { useCategories } from '../api/hooks'
import type { Contact, ContactUpdateRequest } from '../api/types'
import { splitByDirection } from '../lib/categoryColor'
import { CONTACT_IDENTIFIER_HINT } from '../lib/localization'
import { Button } from './Button'
import { categoryOptionElements } from './CategoryOptions'
import { Field, Input } from './Field'
import { Modal } from './Modal'
import { Select } from './Select'

export interface ContactFormSubmitValues {
  name: string
  // null means "no selection" - both directions are independently optional
  // (a contact who's only ever paid, or only ever pays, has no reason to
  // carry a default for the direction that never happens).
  default_category_outflow: string | null
  default_category_inflow: string | null
  identifiers: string[]
}

// Shared by every caller that PATCHes an existing contact with this form's
// output (Contacts.tsx's own edit flow, ReviewDialog.tsx's "the suggested
// identifier already belongs to someone" edit flow). A PATCH's
// default_category_outflow/inflow already mean "leave unchanged" when
// omitted (matching every other field on the request), so the form's own
// "No selection" needs the separate clear_* signal to actually null out a
// previously-set value rather than just omitting it - see
// ContactUpdateRequest's own docstring (api/types.ts) and its backend
// counterpart (models.py).
export function contactSubmitValuesToUpdateBody(body: ContactFormSubmitValues): ContactUpdateRequest {
  return {
    name: body.name,
    identifiers: body.identifiers,
    default_category_outflow: body.default_category_outflow ?? undefined,
    clear_default_category_outflow: body.default_category_outflow == null,
    default_category_inflow: body.default_category_inflow ?? undefined,
    clear_default_category_inflow: body.default_category_inflow == null,
  }
}

// Originally Contacts.tsx-only (create/edit a contact from the Contacts
// page). Pulled out into its own file so the pre-commit review dialog's
// "Save as Contact" action (ReviewDialog.tsx) can open this exact same
// form instead of a one-click checkbox that silently guessed an identifier
// from the raw description - one visual design for "map an identifier to a
// person" instead of a real dialog and a shortcut that drift apart.
//
// The two callers still submit differently underneath (Contacts.tsx always
// creates/updates the contact it was opened for; a review dialog decides
// between the two itself - if the identifier it suggested already belongs
// to someone, it opens THIS SAME form already in edit mode for that
// contact instead of trying to create a second one with a duplicate
// identifier) - `onSubmit` is how that stays the caller's problem rather
// than this component's, mirroring RuleFormModal's onSubmit split.
export function ContactFormModal({
  contact,
  initialName,
  initialIdentifier,
  initialCategoryOutflow,
  initialCategoryInflow,
  onSubmit,
  saving = false,
  onClose,
}: {
  contact?: Contact
  initialName?: string
  initialIdentifier?: string
  initialCategoryOutflow?: string
  initialCategoryInflow?: string
  onSubmit: (body: ContactFormSubmitValues) => Promise<void>
  saving?: boolean
  onClose: () => void
}) {
  const categoriesQ = useCategories()
  const [name, setName] = useState(contact?.name ?? initialName ?? '')
  const [categoryOutflow, setCategoryOutflow] = useState(contact?.default_category_outflow ?? initialCategoryOutflow ?? '')
  const [categoryInflow, setCategoryInflow] = useState(contact?.default_category_inflow ?? initialCategoryInflow ?? '')
  const [identifiers, setIdentifiers] = useState<string[]>(
    contact?.identifiers.length ? contact.identifiers : [initialIdentifier ?? ''],
  )

  const isEditing = contact != null
  const { outflow: outflowCategories, inflow: inflowCategories } = splitByDirection(categoriesQ.data)

  function updateIdentifier(i: number, value: string) {
    setIdentifiers((prev) => prev.map((id, idx) => (idx === i ? value : id)))
  }

  async function handleSave() {
    if (!name.trim()) return
    await onSubmit({
      name: name.trim(),
      default_category_outflow: categoryOutflow || null,
      default_category_inflow: categoryInflow || null,
      identifiers: identifiers.map((i) => i.trim()).filter(Boolean),
    })
    onClose()
  }

  return (
    <Modal onClose={onClose} title={isEditing ? 'Edit Contact' : 'Add Contact'}>
      <Field label="Name" className="mb-3.5">
        <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Auntie Mei" />
      </Field>

      {/* Two independent defaults, not one - a contact who's both paid and
          paid by the same PayNow identifier (a housemate splitting bills, a
          client who's also a supplier) needs each direction to resolve on
          its own. Either (or both) can be left on "No selection". */}
      <div className="flex gap-3 mb-3.5">
        <div className="flex-1 min-w-0">
          <div className="text-xs text-muted mb-1">Default Category · Outflow</div>
          <Select value={categoryOutflow} onChange={(e) => setCategoryOutflow(e.target.value)} className="w-full">
            <option value="">No selection</option>
            {categoryOptionElements(categoriesQ.data, outflowCategories)}
          </Select>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xs text-muted mb-1">Default Category · Inflow</div>
          <Select value={categoryInflow} onChange={(e) => setCategoryInflow(e.target.value)} className="w-full">
            <option value="">No selection</option>
            {categoryOptionElements(categoriesQ.data, inflowCategories)}
          </Select>
        </div>
      </div>

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
