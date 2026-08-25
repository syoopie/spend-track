import { Pencil, Users } from 'lucide-react'
import { useRef, useState } from 'react'
import { useCategories, useContacts, useCreateContact, useImportContactsCsv, useUpdateContact } from '../api/hooks'
import type { Contact } from '../api/types'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { CategoryBadge } from '../components/CategoryBadge'
import { ContactFormModal, contactSubmitValuesToUpdateBody, type ContactFormSubmitValues } from '../components/ContactFormModal'
import { DataTableCell, DataTableHeader, DataTableRow, dataTableGridTemplate, type DataTableColumn } from '../components/DataTable'
import { EmptyState, ErrorState } from '../components/EmptyState'
import { PageShell } from '../components/PageShell'
import { fmtPlain } from '../lib/format'

// contact === undefined -> "Add Contact"; contact set -> "Edit Contact",
// pre-filled and saving via PATCH instead of POST.
function ContactModal({ contact, onClose }: { contact?: Contact; onClose: () => void }) {
  const createContact = useCreateContact()
  const updateContact = useUpdateContact()

  async function handleSubmit(body: ContactFormSubmitValues) {
    if (contact) {
      await updateContact.mutateAsync({ id: contact.id, body: contactSubmitValuesToUpdateBody(body) })
    } else {
      await createContact.mutateAsync(body)
    }
  }

  return (
    <ContactFormModal
      contact={contact}
      onSubmit={handleSubmit}
      saving={createContact.isPending || updateContact.isPending}
      onClose={onClose}
    />
  )
}

const CONTACT_COLUMNS: DataTableColumn[] = [
  { key: 'contact', header: 'Contact', width: '1fr' },
  { key: 'identifiers', header: 'Linked Identifiers', width: '1.6fr' },
  { key: 'category', header: 'Default Category', width: '160px' },
  { key: 'spend', header: 'Spent', width: '110px', align: 'right' },
  { key: 'received', header: 'Received', width: '110px', align: 'right' },
  { key: 'actions', header: '', width: '36px' },
]
const CONTACT_GRID_TEMPLATE = dataTableGridTemplate(CONTACT_COLUMNS)

export function Contacts() {
  const contactsQ = useContacts()
  const categoriesQ = useCategories()
  const importCsv = useImportContactsCsv()
  const fileInputRef = useRef<HTMLInputElement>(null)
  // 'new' opens the modal in Add mode; a Contact opens it pre-filled in Edit mode.
  const [formTarget, setFormTarget] = useState<Contact | 'new' | null>(null)

  return (
    <PageShell
      title="Contacts & PayNow Directory"
      subtitle="Map phone numbers and UENs to people, so transfers categorize themselves"
      icon={Users}
      actions={
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) importCsv.mutate(file)
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
      <Card padding="" className="overflow-hidden" role="grid" aria-label="Contacts">
        <DataTableHeader
          columns={CONTACT_COLUMNS}
          gridTemplate={CONTACT_GRID_TEMPLATE}
          className="px-5 py-2.5 text-2xs text-muted-2 uppercase tracking-wide border-b border-divider"
        />
        {contactsQ.isLoading && <div className="p-5 text-muted text-sm">Loading…</div>}
        {contactsQ.isError && (
          <ErrorState description="Couldn't load your contacts." onRetry={() => contactsQ.refetch()} />
        )}
        {contactsQ.isSuccess && (contactsQ.data ?? []).length === 0 && (
          <EmptyState
            icon={Users}
            title="No contacts yet"
            description="Map a phone number or UEN to a name so PayNow transfers categorize themselves."
            action={
              <Button variant="primary" size="sm" onClick={() => setFormTarget('new')}>
                + Add Contact
              </Button>
            }
          />
        )}
        {(contactsQ.data ?? []).map((c) => (
          <DataTableRow key={c.id} gridTemplate={CONTACT_GRID_TEMPLATE} className="items-center px-5 py-3.5 text-md border-b border-divider">
            <DataTableCell className="font-semibold">{c.name}</DataTableCell>
            <DataTableCell>
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
            </DataTableCell>
            <DataTableCell>
              {c.default_category_outflow == null && c.default_category_inflow == null ? (
                <span className="text-muted-2 text-xs">—</span>
              ) : (
                <div className="flex flex-col gap-1 items-start">
                  {c.default_category_outflow != null && (
                    <CategoryBadge category={c.default_category_outflow} categories={categoriesQ.data} />
                  )}
                  {c.default_category_inflow != null && (
                    <CategoryBadge category={c.default_category_inflow} categories={categoriesQ.data} />
                  )}
                </div>
              )}
            </DataTableCell>
            <DataTableCell align="right" className="font-mono">
              {fmtPlain(c.historical_spend)}
            </DataTableCell>
            <DataTableCell align="right" className="font-mono">
              {fmtPlain(c.historical_received)}
            </DataTableCell>
            <DataTableCell align="right">
              <button
                onClick={() => setFormTarget(c)}
                title="Edit contact"
                className="text-muted hover:text-text bg-transparent border-none cursor-pointer p-1 rounded-md"
              >
                <Pencil size={14} />
              </button>
            </DataTableCell>
          </DataTableRow>
        ))}
      </Card>

      {formTarget && (
        <ContactModal contact={formTarget === 'new' ? undefined : formTarget} onClose={() => setFormTarget(null)} />
      )}
    </PageShell>
  )
}
