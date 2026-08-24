import { categoryColor, categoryIcon } from '../lib/categoryColor'
import type { Category } from '../api/types'

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
