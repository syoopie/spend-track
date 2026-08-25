export type DirectionFilter = 'inflow' | 'outflow'

export interface DashboardFilters {
  range?: { from: string; to: string }
  accountId?: string
  showFullName?: boolean
  searchText?: string
  categoryFilter?: string
  excludedVisible?: boolean
  direction?: DirectionFilter
}

const STORAGE_KEY = 'sg-tracker-dashboard-filters'

export function loadDashboardFilters(): DashboardFilters {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    const range =
      parsed.range && typeof parsed.range.from === 'string' && typeof parsed.range.to === 'string'
        ? { from: parsed.range.from, to: parsed.range.to }
        : undefined
    const accountId = typeof parsed.accountId === 'string' ? parsed.accountId : undefined
    const showFullName = typeof parsed.showFullName === 'boolean' ? parsed.showFullName : undefined
    const searchText = typeof parsed.searchText === 'string' ? parsed.searchText : undefined
    const categoryFilter = typeof parsed.categoryFilter === 'string' ? parsed.categoryFilter : undefined
    const excludedVisible = typeof parsed.excludedVisible === 'boolean' ? parsed.excludedVisible : undefined
    const direction =
      parsed.direction === 'inflow' || parsed.direction === 'outflow' ? (parsed.direction as DirectionFilter) : undefined
    return { range, accountId, showFullName, searchText, categoryFilter, excludedVisible, direction }
  } catch {
    return {}
  }
}

export function saveDashboardFilters(filters: DashboardFilters): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filters))
}
