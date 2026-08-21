import {
  Banknote,
  Bus,
  Clapperboard,
  Dumbbell,
  GraduationCap,
  HeartPulse,
  Home,
  MoreHorizontal,
  Receipt,
  Send,
  ShoppingBag,
  ShoppingCart,
  Sparkles,
  Tag,
  TrendingUp,
  Utensils,
  type LucideIcon,
} from 'lucide-react'
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
}

export function categoryIcon(categories: Category[] | undefined, name: string): LucideIcon {
  const icon = categories?.find((c) => c.name === name)?.icon
  return (icon && ICON_COMPONENTS[icon]) || Tag
}
