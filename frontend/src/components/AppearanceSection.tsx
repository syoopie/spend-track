import { useState } from 'react'
import { ACCENT_PRESETS, DEFAULT_ACCENT, loadStoredAccentColor, resetAccentColor, saveAccentColor } from '../lib/accentColor'

// Entirely frontend-only - accent color persists to localStorage, there's no
// backend endpoint for it at all (see CONTEXT.md's Data lifecycle entry).
export function AppearanceSection() {
  const [accent, setAccent] = useState(loadStoredAccentColor())

  function pick(hex: string) {
    setAccent(hex)
    saveAccentColor(hex)
  }

  function reset() {
    setAccent(DEFAULT_ACCENT)
    resetAccentColor()
  }

  return (
    <div className="bg-card border border-border rounded-xl p-5 mb-4">
      <div className="text-[13px] font-semibold mb-1">Appearance</div>
      <div className="text-xs text-muted mb-3.5">Choose the accent color used for buttons, links, and highlights.</div>
      <div className="flex items-center gap-2.5 flex-wrap">
        {ACCENT_PRESETS.map((p) => (
          <button
            key={p.hex}
            onClick={() => pick(p.hex)}
            title={p.name}
            className="w-7 h-7 rounded-full cursor-pointer"
            style={{
              background: p.hex,
              outline: accent.toLowerCase() === p.hex.toLowerCase() ? '2px solid var(--color-text)' : 'none',
              outlineOffset: 2,
              border: 'none',
            }}
          />
        ))}
        <label
          title="Custom color"
          className="relative w-7 h-7 rounded-full cursor-pointer border border-border overflow-hidden flex items-center justify-center"
          style={{
            background: ACCENT_PRESETS.some((p) => p.hex.toLowerCase() === accent.toLowerCase())
              ? 'conic-gradient(from 0deg, #e35fd0, #a78bfa, #5b9dff, #2dd4bf, #4ade80, #fbbf24, #fb923c, #f87171, #e35fd0)'
              : accent,
          }}
        >
          <input
            type="color"
            value={accent}
            onChange={(e) => pick(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer"
          />
        </label>
        <button
          onClick={reset}
          className="text-[12px] text-muted hover:text-text cursor-pointer border-none bg-transparent ml-1"
        >
          Reset to default
        </button>
      </div>
    </div>
  )
}
