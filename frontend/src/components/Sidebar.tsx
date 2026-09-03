import { BookOpen, HeartHandshake, LayoutGrid, ListChecks, Pin, PinOff, Settings as SettingsIcon, SlidersHorizontal, Upload, Users } from 'lucide-react'
import { useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useSettings } from '../api/hooks'
import { Logo } from './Logo'
import { useUploadDialog } from './UploadProvider'

const NAV_ITEMS = [
  {
    to: '/',
    label: 'Dashboard',
    icon: <LayoutGrid size={16} className="shrink-0" />,
  },
  {
    to: '/contacts',
    label: 'Contacts',
    icon: <Users size={16} className="shrink-0" />,
  },
  {
    to: '/rules',
    label: 'Rules',
    icon: <SlidersHorizontal size={16} className="shrink-0" />,
  },
  {
    to: '/default-rules',
    label: 'Default Rules',
    icon: <ListChecks size={16} className="shrink-0" />,
  },
  {
    to: '/guide',
    label: 'User Guide',
    icon: <BookOpen size={16} className="shrink-0" />,
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: <SettingsIcon size={16} className="shrink-0" />,
  },
]

const PIN_STORAGE_KEY = 'sidebar-pinned'
// Waits for a deliberate hover, not a passing cursor swipe near the left
// edge, before expanding (X-5 in UI Review.dc.html) - the rail used to open
// on any incidental pointer pass, covering the first metric card.
const HOVER_INTENT_MS = 200

function loadPinned(): boolean {
  try {
    return localStorage.getItem(PIN_STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function Sidebar() {
  const { openDialog, hasPendingBatch } = useUploadDialog()
  const settingsQ = useSettings()
  // The "local-only" claim stops being true the moment a cloud AI provider
  // is active - this footer must reflect that rather than keep asserting it
  // unconditionally. See Settings' AI section for where this is configured.
  const usingCloudAi = !!settingsQ.data?.ai_enabled && settingsQ.data?.ai_provider !== 'ollama'

  const [pinned, setPinned] = useState(loadPinned)
  const [hovering, setHovering] = useState(false)
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Pinned or genuinely hovered (past the intent delay) - the one flag
  // every collapsed/expanded conditional below reads, so the pinned state
  // and the hover state can never visually disagree with each other.
  const expanded = pinned || hovering

  function handleMouseEnter() {
    if (pinned) return
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    hoverTimer.current = setTimeout(() => setHovering(true), HOVER_INTENT_MS)
  }
  function handleMouseLeave() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current)
    setHovering(false)
  }

  function togglePinned() {
    setPinned((prev) => {
      const next = !prev
      try {
        localStorage.setItem(PIN_STORAGE_KEY, next ? '1' : '0')
      } catch {
        // localStorage unavailable (private mode, etc.) - the toggle still
        // works for this session, it just won't survive a reload.
      }
      return next
    })
    setHovering(false)
  }

  return (
    // Pinned reserves 240px in the layout itself (the panel becomes a
    // normal in-flow sibling, pushing the page content over) instead of
    // absolutely overlaying it - X-5's "covers the first metric card"
    // complaint was specifically about the unpinned hover-overlay doing
    // this unconditionally. Unpinned still reserves the collapsed 64px so
    // hovering never reflows anything to its right.
    <div className={`shrink-0 relative ${pinned ? 'w-60' : 'w-16'}`}>
      <div
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={`${pinned ? 'absolute inset-y-0 left-0 w-60' : `absolute inset-y-0 left-0 z-30 ${expanded ? 'w-60' : 'w-16'}`}
          bg-sidebar text-muted flex flex-col p-3.5 border-r border-border overflow-hidden transition-[width] duration-200 ease-out`}
      >
        {/* Every row's icon sits in a fixed-width ICON_SLOT (w-9 = 36px,
            exactly the rail's collapsed content width: 64px rail - 14px
            padding on each side) instead of being positioned by the row's
            own horizontal padding. Centering the icon *within* that slot -
            rather than left-padding it - is what makes icons of different
            sizes (the 26px logo square vs. 15-18px nav icons) all land on
            the rail's true center when collapsed. The slot's width and
            position never change between collapsed/expanded, so icons don't
            shift when the rail opens - only the label past it grows.
            Labels still sit in a w-0 (collapsed) / w-auto (expanded)
            wrapper with its own overflow-hidden - explicit zero width at
            rest, rather than relying on leftover space rounding down to
            nothing (it didn't: a few px of slack let a sliver of every
            label bleed through while collapsed). Driven by the `expanded`
            flag now, not CSS :hover, so pinning and the hover-intent delay
            both take effect the same way. */}
        <div className="flex items-center justify-between pt-1.5 pb-5.5">
          <NavLink to="/" end className="flex items-center gap-2 min-w-0">
            <div className="w-9 flex items-center justify-center shrink-0">
              <Logo size={26} />
            </div>
            <div className={`overflow-hidden shrink-0 ${expanded ? 'w-auto' : 'w-0'}`}>
              <div className="text-sm font-semibold font-display text-text leading-tight whitespace-nowrap">
                Spend
                <br />
                Track
              </div>
            </div>
          </NavLink>
          {expanded && (
            <button
              onClick={togglePinned}
              title={pinned ? 'Unpin sidebar' : 'Pin sidebar open'}
              className="shrink-0 p-1 rounded-md border-none bg-transparent text-muted-2 hover:text-text cursor-pointer"
            >
              {pinned ? <PinOff size={14} /> : <Pin size={14} />}
            </button>
          )}
        </div>

        <button
          onClick={openDialog}
          disabled={hasPendingBatch}
          title={
            hasPendingBatch
              ? 'Review the pending statement before uploading another'
              : 'Upload a bank statement PDF - or drag & drop one anywhere in the app, anytime'
          }
          className="flex items-center gap-1.5 py-2.5 mb-4 rounded-lg text-sm font-semibold border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <div className="w-9 flex items-center justify-center shrink-0">
            <Upload size={15} />
          </div>
          <span className={`overflow-hidden shrink-0 whitespace-nowrap ${expanded ? 'w-auto' : 'w-0'}`}>
            Upload Bank Statement
          </span>
        </button>

        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            title={item.label}
            className={({ isActive }) =>
              `relative flex items-center gap-2 py-2.5 rounded-lg text-sm font-medium mb-0.5 ${
                isActive ? 'text-text bg-accent/12' : 'text-nav hover:bg-nav-hover'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {/* A stronger active indicator than the background tint
                    alone (X-5) - a 3px bar pinned to the rail's true left
                    edge (not the row's own edge, which shifts if the row
                    ever gets its own padding) so it reads the same whether
                    the rail is collapsed or expanded. */}
                {isActive && <span className="absolute -left-3.5 top-1 bottom-1 w-[3px] rounded-r bg-accent" />}
                <div className="w-9 flex items-center justify-center shrink-0">{item.icon}</div>
                <span className={`overflow-hidden shrink-0 whitespace-nowrap ${expanded ? 'w-auto' : 'w-0'}`}>
                  {item.label}
                </span>
              </>
            )}
          </NavLink>
        ))}

        <div className="flex-1" />
        {/* Deliberately not a NAV_ITEMS row. The six above are things you do
            weekly; this is a thing you do once, if ever. It keeps the w-9
            icon slot so the collapsed rail still lines up, but drops the
            accent bar and the tinted active background that make those six
            read as destinations. */}
        <NavLink
          to="/contribute"
          title="Help add your bank"
          className={({ isActive }) =>
            `flex items-start text-2xs pt-2.5 pb-2 border-t border-border ${isActive ? 'text-text' : 'text-muted-2 hover:text-text'}`
          }
        >
          <div className="w-9 h-4 flex items-center justify-center shrink-0">
            <HeartHandshake size={13} className="shrink-0" />
          </div>
          <div className={`overflow-hidden shrink-0 ${expanded ? 'w-auto' : 'w-0'}`}>
            <div className="w-[160px] leading-snug">Help add your bank</div>
          </div>
        </NavLink>
        <div className="flex items-start text-2xs text-muted-2">
          <div className="w-9 h-4 flex items-center justify-center shrink-0">
            <span className={`w-1.5 h-1.5 rounded-full ${usingCloudAi ? 'bg-accent' : 'bg-success'}`} />
          </div>
          {/* Fixed width so it wraps onto two lines instead of rendering as
              one long line that crowds (or overflows past) the rail's right
              edge - "w-auto" alone would size to the text's full one-line
              width, same trap the old caption had before it got a fixed
              width too. */}
          <div className={`overflow-hidden shrink-0 ${expanded ? 'w-auto' : 'w-0'}`}>
            <div className="w-[160px] leading-snug">
              {usingCloudAi ? 'Cloud AI enabled · some data leaves this device' : 'Local-only · no data leaves this device'}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
