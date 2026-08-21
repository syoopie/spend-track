import { categoryIcon, splitByDirection } from '../lib/categoryColor'
import type { Category } from '../api/types'

/** Builds the full category list as <option> elements for a <Select>,
 * grouped into two visually separated blocks (Outflow / Inflow) - for
 * pickers that don't have a single transaction amount to filter by (a
 * rule or a contact's default category can apply to either direction), so
 * both halves stay visible instead of flattening into one undifferentiated
 * list. A plain function, not a component - it must be *called* inline
 * inside <Select>'s children (`{categoryOptionElements(...)}`), not
 * rendered as a JSX tag, since <Select> only recognizes literal <option>
 * elements among its direct children. */
export function categoryOptionElements(categories: Category[] | undefined) {
  const { outflow, inflow } = splitByDirection(categories)

  function renderOption(c: Category) {
    const Icon = categoryIcon(categories, c.name)
    return (
      <option key={c.id} value={c.name}>
        <Icon size={12} className="shrink-0" /> {c.name}
      </option>
    )
  }

  return [
    ...(outflow.length > 0
      ? [
          <option key="__outflow_divider__" value="__outflow_divider__" disabled>
            — Outflow —
          </option>,
        ]
      : []),
    ...outflow.map(renderOption),
    ...(inflow.length > 0
      ? [
          <option key="__inflow_divider__" value="__inflow_divider__" disabled>
            — Inflow —
          </option>,
        ]
      : []),
    ...inflow.map(renderOption),
  ]
}
