import { ChevronDown, ChevronUp, ChevronsUpDown } from 'lucide-react'
import type { ReactNode } from 'react'

// X-6 in UI Review.dc.html: every grid list in the app (the transaction
// feed, Contacts, the review dialogs) hand-rolled its own column-width
// string and header row. This centralizes just the column *template* (one
// array drives both the header and, via dataTableGridClass, the row grid a
// caller renders) plus real ARIA table semantics for the header.
//
// Deliberately NOT a data-driven `render(row) => ReactNode` table that also
// owns row rendering: the feed and the review dialogs' rows are each a
// single `role="button"` disclosure/edit control (arrow-key navigation,
// aria-expanded, a click that opens a popover) - a legitimate, already-
// accessible pattern in its own right, but not the ARIA grid-row pattern.
// Forcing role="row"/role="gridcell" onto an element that's already
// role="button" would misdescribe what it actually is, not fix an
// accessibility gap. Those callers use DataTableHeader for a real
// role="row"/role="columnheader" header and dataTableGridClass for the
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

export function dataTableGridClass(columns: DataTableColumn<string>[]): string {
  return `grid-cols-[${columns.map((c) => c.width).join('_')}]`
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
  gridClassName,
  className = '',
  sort,
  onSort,
  headerRef,
}: {
  columns: DataTableColumn<F>[]
  gridClassName: string
  className?: string
  sort?: { field: F; dir: 'asc' | 'desc' }
  onSort?: (field: F) => void
  headerRef?: React.Ref<HTMLDivElement>
}) {
  return (
    <div ref={headerRef} role="row" className={`grid ${gridClassName} ${className}`}>
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
  gridClassName,
  className = '',
  children,
}: {
  gridClassName: string
  className?: string
  children: ReactNode
}) {
  return (
    <div role="row" className={`grid ${gridClassName} ${className}`}>
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
