export interface DashboardFilters {
  range?: { from: string; to: string }
  accountId?: string
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
    return { range, accountId }
  } catch {
    return {}
  }
}

export function saveDashboardFilters(filters: DashboardFilters): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filters))
}
