import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react'
import type { ReactNode } from 'react'

// X-6 in UI Review.dc.html: every grid list in the app (the transaction
// feed, Contacts, the review dialogs) hand-rolled its own column-width
// string and header row. This centralizes just the column *template* (one
// array drives both the header and, via dataTableGridTemplate, the row grid
// a caller renders) plus real ARIA table semantics for the header.
//
// Deliberately NOT a data-driven `render(row) => ReactNode` table that also
// owns row rendering: the feed and the review dialogs' rows are each a
// single `role="button"` disclosure/edit control (arrow-key navigation,
// aria-expanded, a click that opens a popover) - a legitimate, already-
// accessible pattern in its own right, but not the ARIA grid-row pattern.
// Forcing role="row"/role="gridcell" onto an element that's already
// role="button" would misdescribe what it actually is, not fix an
// accessibility gap. Those callers use DataTableHeader for a real
// role="row"/role="columnheader" header and dataTableGridTemplate for the
// shared column template, and keep their own row markup exactly as before.
// Contacts' rows are plain (only the trailing edit button is interactive),
// a genuine fit for full row/gridcell semantics too - see its own usage.
export interface DataTableColumn<F extends string = never> {
  key: string
  header: ReactNode
  // A raw grid-template-columns track, e.g. "76px", "minmax(0,1fr)", "28px".
  width: string
  align?: 'left' | 'right'
  // Present only on columns that should render as a sort trigger - matches
  // whatever field type the caller's own sort state uses.
  sortKey?: F
}

// Returns the raw `grid-template-columns` value for an inline style, NOT a
// Tailwind class - a `grid-cols-[...]` class built from this string used to
// be handed to `className` instead, but Tailwind's scanner only recognizes
// arbitrary-value classes that appear as a literal, complete substring
// somewhere in the source text it scans; one assembled at runtime from an
// array (like this) never does, so `grid-cols-[...]` had no matching CSS
// rule at all. It silently "worked" through most of one long dev session
// only because Tailwind's dev-mode output is additive and an earlier,
// literal version of the same string (before this got extracted into a
// shared column-template array) was still sitting in the generated
// stylesheet from before that change - restarting the dev server (a fresh
// scan, nothing left over) or a real production build (which always scans
// fresh) exposed every column collapsing to a single stacked line. `style`
// has no such constraint since it's just a DOM property, not a class Tailwind
// needs to have pre-generated.
export function dataTableGridTemplate(columns: DataTableColumn<string>[]): string {
  return columns.map((c) => c.width).join(' ')
}

function SortHeaderButton<F extends string>({
  field,
  label,
  align,
  active,
  dir,
  onSort,
}: {
  field: F
  label: ReactNode
  align?: 'left' | 'right'
  active: boolean
  dir: 'asc' | 'desc'
  onSort: (field: F) => void
}) {
  const Icon = active ? (dir === 'asc' ? ChevronUp : ChevronDown) : ChevronsUpDown
  return (
    <button
      type="button"
      onClick={() => onSort(field)}
      className={`inline-flex items-center gap-1 bg-transparent border-none cursor-pointer p-0 text-2xs uppercase tracking-wide hover:text-text ${
        active ? 'text-text' : 'text-muted-2'
      } ${align === 'right' ? 'justify-end w-full' : ''}`}
    >
      {label}
      <Icon size={11} className="shrink-0" />
    </button>
  )
}

export function DataTableHeader<F extends string>({
  columns,
  gridTemplate,
  className = '',
  sort,
  onSort,
  headerRef,
}: {
  columns: DataTableColumn<F>[]
  gridTemplate: string
  className?: string
  sort?: { field: F; dir: 'asc' | 'desc' }
  onSort?: (field: F) => void
  headerRef?: React.Ref<HTMLDivElement>
}) {
  return (
    <div ref={headerRef} role="row" className={`grid ${className}`} style={{ gridTemplateColumns: gridTemplate }}>
      {columns.map((col) => (
        <div
          key={col.key}
          role="columnheader"
          className={col.align === 'right' ? 'text-right' : undefined}
        >
          {col.sortKey && onSort && sort ? (
            <SortHeaderButton
              field={col.sortKey}
              label={col.header}
              align={col.align}
              active={sort.field === col.sortKey}
              dir={sort.dir}
              onSort={onSort}
            />
          ) : (
            col.header
          )}
        </div>
      ))}
    </div>
  )
}

// For the genuine-grid case (Contacts) where a data row has no competing
// role of its own - wraps children (one per column, caller's own order) in
// role="row"/role="gridcell" using the same column template as the header.
export function DataTableRow({
  gridTemplate,
  className = '',
  children,
}: {
  gridTemplate: string
  className?: string
  children: ReactNode
}) {
  return (
    <div role="row" className={`grid ${className}`} style={{ gridTemplateColumns: gridTemplate }}>
      {children}
    </div>
  )
}

export function DataTableCell({
  align,
  className = '',
  children,
}: {
  align?: 'left' | 'right'
  className?: string
  children: ReactNode
}) {
  return (
    <div role="gridcell" className={`${align === 'right' ? 'text-right' : ''} ${className}`}>
      {children}
    </div>
  )
}
