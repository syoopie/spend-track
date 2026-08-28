/**
 * Categories that are one concept the schema had to split in two.
 *
 * `categories.direction` is a hard property - a category belongs to inflow or
 * to outflow, never both (see schema.sql, and migrations.py's own note on the
 * three categories that used to straddle the line). That split is right for
 * categorization: money paid out through PayNow and money received through it
 * are genuinely different rows to reason about, and a rule targeting one must
 * not fire on the other.
 *
 * It is wrong for *filtering*, which is a reading question rather than a
 * writing one. Someone who picks "Paynow" is asking to see their PayNow
 * activity, and the fact that the picker lists it under Outflow is an
 * implementation detail of the categorization engine leaking into a filter.
 *
 * A name-keyed list rather than a column on `categories`: the pairing is a
 * property of this profile's *built-in* categories, all of which are defined
 * by name in one place already (migrations.py's DEFAULT_CATEGORIES, mirrored
 * by the fallback names hardcoded in engine/rules.py). A user-created
 * category has no counterpart and needs none, so there is nothing for a
 * column to hold for it.
 */
const PAIRS: readonly (readonly [string, string])[] = [
  ['Paynow', 'Paynow Received'],
  // Both halves of the fallback - a transaction no rule matched, in either
  // direction. ReviewDialog.tsx already treats these two as one thing when
  // deciding what counts as uncategorized.
  ['Others', 'Other Income'],
]

/** The other half of `name`'s pair, or null when it stands alone. */
export function categoryPartner(name: string): string | null {
  for (const [outflow, inflow] of PAIRS) {
    if (name === outflow) return inflow
    if (name === inflow) return outflow
  }
  return null
}

/** `name` plus its counterpart, if it has one - what a filter on `name`
 *  should actually cover. */
export function pairedCategories(name: string): string[] {
  const partner = categoryPartner(name)
  return partner ? [name, partner] : [name]
}

/** Whether a transaction in `category` belongs in a list filtered to
 *  `filter`. Exact match, widened to the pair. */
export function categoryFilterMatches(filter: string, category: string): boolean {
  return category === filter || categoryPartner(filter) === category
}
