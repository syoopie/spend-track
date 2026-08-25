import { categoryColor, categoryDotColor, categoryIcon } from '../lib/categoryColor'
import type { Category } from '../api/types'

/** A category as a colored pill - for tables and rows, where the category is
 * one column among many and needs to be findable at a glance. */
export function CategoryBadge({
  category,
  categories,
  colorOverride,
}: {
  category: string
  categories: Category[] | undefined
  colorOverride?: { bg: string; fg: string }
}) {
  const cc = colorOverride ?? categoryColor(categories, category)
  const Icon = categoryIcon(categories, category)
  return (
    <span
      className="inline-flex items-center gap-1 text-2xs px-2 py-0.5 rounded-md max-w-full min-w-0"
      style={{ background: cc.bg, color: cc.fg }}
      title={category}
    >
      <Icon size={11} className="shrink-0" />
      <span className="truncate">{category}</span>
    </span>
  )
}

/** The same category, minus the pill - for a picker's options or a filter
 * chip, where a second background inside an existing surface reads as noise.
 * Icon-and-name is the app's one way of writing a category, so anywhere a
 * category name would otherwise be bare text goes through this or
 * `CategoryBadge`, never a hand-typed `{name}`. */
export function CategoryLabel({
  category,
  categories,
  size = 12,
  tinted = false,
}: {
  category: string
  categories: Category[] | undefined
  size?: number
  /** Colors the icon with the category's own hue - worth it where the label
   * sits alone (a filter chip), noise where a whole list of them would turn
   * a dropdown into a rainbow. */
  tinted?: boolean
}) {
  const Icon = categoryIcon(categories, category)
  return (
    <span className="inline-flex items-center gap-1.5">
      <Icon
        size={size}
        className="shrink-0"
        style={tinted ? { color: categoryDotColor(categories, category) } : undefined}
      />
      {category}
    </span>
  )
}
