import {
  Banknote,
  Bus,
  Clapperboard,
  Download,
  Dumbbell,
  GraduationCap,
  HeartPulse,
  Home,
  MoreHorizontal,
  PiggyBank,
  Plane,
  Receipt,
  Send,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Tag,
  TrendingUp,
  Undo2,
  Utensils,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import type { Category, CategoryDirection } from '../api/types'

export function categoryColor(categories: Category[] | undefined, name: string): { bg: string; fg: string } {
  const hue = categories?.find((c) => c.name === name)?.hue
  if (hue === null || hue === undefined) return { bg: '#22232c', fg: '#9b9ba8' }
  return { bg: `oklch(26% 0.05 ${hue})`, fg: `oklch(78% 0.15 ${hue})` }
}

export function categoryDotColor(categories: Category[] | undefined, name: string): string {
  const hue = categories?.find((c) => c.name === name)?.hue
  return hue === null || hue === undefined ? '#3a3b48' : `oklch(72% 0.14 ${hue})`
}

const ICON_COMPONENTS: Record<string, LucideIcon> = {
  dumbbell: Dumbbell,
  sparkles: Sparkles,
  utensils: Utensils,
  'shopping-bag': ShoppingBag,
  bus: Bus,
  home: Home,
  receipt: Receipt,
  clapperboard: Clapperboard,
  'heart-pulse': HeartPulse,
  'graduation-cap': GraduationCap,
  'shopping-cart': ShoppingCart,
  banknote: Banknote,
  'trending-up': TrendingUp,
  send: Send,
  'more-horizontal': MoreHorizontal,
  'undo-2': Undo2,
  'piggy-bank': PiggyBank,
  plane: Plane,
  download: Download,
  wallet: Wallet,
}

export function categoryIcon(categories: Category[] | undefined, name: string): LucideIcon {
  const icon = categories?.find((c) => c.name === name)?.icon
  return (icon && ICON_COMPONENTS[icon]) || Tag
}

/** Splits a category list into its outflow and inflow halves, each still in
 * their existing sort_order - categories are direction-locked (see
 * schema.sql's categories.direction), so this partition is exhaustive and
 * exclusive, never overlapping. */
export function splitByDirection(categories: Category[] | undefined): Record<CategoryDirection, Category[]> {
  const outflow: Category[] = []
  const inflow: Category[] = []
  for (const c of categories ?? []) {
    ;(c.direction === 'inflow' ? inflow : outflow).push(c)
  }
  return { outflow, inflow }
}
