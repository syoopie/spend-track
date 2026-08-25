/** The app mark: three bars on a baseline, on the same rounded tile the
 * rest of the UI is built from.
 *
 * Painted from the accent tokens rather than fixed hex, so it re-tints with
 * whatever accent the user picked under Settings - the static copies
 * (`public/favicon.svg`, `docs/logo.svg`) carry the default pink, since a
 * file on disk can't follow a CSS variable.
 *
 * Bar heights are deliberately short-tall-medium rather than a clean ramp:
 * an ascending staircase reads as a signal-strength icon at favicon size,
 * where an uneven set reads as a chart. */
export function Logo({ size = 26, className = '' }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="SpendTrack"
    >
      <rect width="32" height="32" rx="8" fill="var(--color-accent)" />
      <g fill="var(--color-accent-fg)">
        <rect x="7.5" y="15.5" width="4.5" height="7" rx="1.6" />
        <rect x="13.75" y="7.5" width="4.5" height="15" rx="1.6" />
        <rect x="20" y="11.5" width="4.5" height="11" rx="1.6" />
      </g>
      <rect x="7.5" y="23.5" width="17" height="1.5" rx="0.75" fill="var(--color-accent-fg)" opacity="0.45" />
    </svg>
  )
}
