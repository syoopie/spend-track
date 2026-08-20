import type { Category } from '../api/types'

export function categoryColor(categories: Category[] | undefined, name: string): { bg: string; fg: string } {
  const hue = categories?.find((c) => c.name === name)?.hue
  if (hue === null || hue === undefined) return { bg: '#22232c', fg: '#9b9ba8' }
  return { bg: `oklch(26% 0.05 ${hue})`, fg: `oklch(78% 0.15 ${hue})` }
}

export function categoryDotColor(categories: Category[] | undefined, name: string): string {
  const hue = categories?.find((c) => c.name === name)?.hue
  return hue === null || hue === undefined ? '#3a3b48' : `oklch(72% 0.14 ${hue})`
}
