import type { ReactNode } from 'react'

export function Modal({
  onClose,
  children,
  width = 440,
}: {
  onClose: () => void
  children: ReactNode
  width?: number
}) {
  return (
    <div
      onClick={onClose}
      className="fixed inset-0 bg-black/55 z-50 flex items-center justify-center"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-card border border-border rounded-2xl p-6.5"
        style={{ width }}
      >
        {children}
      </div>
    </div>
  )
}
