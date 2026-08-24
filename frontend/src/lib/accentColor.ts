export const DEFAULT_ACCENT = '#e35fd0'

const STORAGE_KEY = 'sg-tracker-accent-color'

export const ACCENT_PRESETS = [
  { name: 'Pink', hex: '#e35fd0' },
  { name: 'Violet', hex: '#a78bfa' },
  { name: 'Blue', hex: '#5b9dff' },
  { name: 'Teal', hex: '#2dd4bf' },
  { name: 'Green', hex: '#4ade80' },
  { name: 'Amber', hex: '#fbbf24' },
  { name: 'Orange', hex: '#fb923c' },
  { name: 'Red', hex: '#f87171' },
]

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const m = hex.replace('#', '')
  const full = m.length === 3 ? m.split('').map((c) => c + c).join('') : m
  const n = parseInt(full, 16)
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 }
}

function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)))
  return '#' + [r, g, b].map((v) => clamp(v).toString(16).padStart(2, '0')).join('')
}

function mix(hexA: string, hexB: string, t: number): string {
  const a = hexToRgb(hexA)
  const b = hexToRgb(hexB)
  return rgbToHex(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t)
}

function relativeLuminance(hex: string): number {
  const { r, g, b } = hexToRgb(hex)
  const [rl, gl, bl] = [r, g, b].map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
}

function contrastRatio(hexA: string, hexB: string): number {
  const lA = relativeLuminance(hexA)
  const lB = relativeLuminance(hexB)
  const lighter = Math.max(lA, lB)
  const darker = Math.min(lA, lB)
  return (lighter + 0.05) / (darker + 0.05)
}

// WCAG AA for normal-size text/icons on a solid fill.
const MIN_CONTRAST = 4.5

// Whichever ink (near-black vs near-white) contrasts better against `hex` -
// what the accent-foreground token actually uses. Exported so the Appearance
// picker can warn when even the *better* of the two options still falls
// short (SET-5 in UI Review.dc.html) - a custom color close to mid-grey can
// fail 4.5:1 against both, not just the one a fixed dark ink would have
// picked.
export function bestAccentForeground(hex: string): { fg: string; contrast: number } {
  const dark = '#1a0e18'
  const light = '#f3f3f6'
  const darkContrast = contrastRatio(hex, dark)
  const lightContrast = contrastRatio(hex, light)
  return darkContrast >= lightContrast ? { fg: dark, contrast: darkContrast } : { fg: light, contrast: lightContrast }
}

export function hasLowContrast(hex: string): boolean {
  return bestAccentForeground(hex).contrast < MIN_CONTRAST
}

export function applyAccentColor(hex: string): void {
  const root = document.documentElement
  root.style.setProperty('--color-accent', hex)
  root.style.setProperty('--color-accent-hover', mix(hex, '#ffffff', 0.22))
  root.style.setProperty('--color-accent-fg', bestAccentForeground(hex).fg)
}

export function loadStoredAccentColor(): string {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_ACCENT
}

export function saveAccentColor(hex: string): void {
  localStorage.setItem(STORAGE_KEY, hex)
  applyAccentColor(hex)
}

export function resetAccentColor(): void {
  localStorage.removeItem(STORAGE_KEY)
  applyAccentColor(DEFAULT_ACCENT)
}
