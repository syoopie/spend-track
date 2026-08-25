import { splitByDirection } from '../lib/categoryColor'
import type { Category } from '../api/types'
import { CategoryLabel } from './CategoryBadge'

/** A single <option> for a category name that may not be in the list at all -
 * a transaction still carrying a category that's since been renamed or
 * removed. `categoryIcon` falls back to a generic tag icon, so even an
 * unknown value keeps the same shape as its neighbours instead of being the
 * one bare-text row in the panel. */
export function categoryOption(categories: Category[] | undefined, name: string) {
  return (
    <option key={name} value={name}>
      <CategoryLabel category={name} categories={categories} />
    </option>
  )
}

/** Builds category <option> elements for a <Select>.
 *
 * With no `subset`, the full list is grouped into two visually separated
 * blocks (Outflow / Inflow) - for pickers with no single transaction
 * direction to filter by (a rule, a contact's default category, a filter, or
 * a bulk edit over a mixed selection can each apply to either direction), so
 * both halves stay visible instead of flattening into one undifferentiated
 * list.
 *
 * Pass `subset` (already direction-filtered by the caller) for a per-row
 * picker where only one direction is valid; those render flat, since a
 * divider over a single block is noise.
 *
 * A plain function, not a component - it must be *called* inline inside
 * <Select>'s children (`{categoryOptionElements(...)}`), not rendered as a
 * JSX tag, since <Select> only recognizes literal <option> elements among
 * its direct children. */
export function categoryOptionElements(categories: Category[] | undefined, subset?: Category[]) {
  function renderOption(c: Category) {
    return (
      <option key={c.id} value={c.name}>
        <CategoryLabel category={c.name} categories={categories} />
      </option>
    )
  }

  if (subset) return subset.map(renderOption)

  const { outflow, inflow } = splitByDirection(categories)
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
