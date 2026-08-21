import { BookOpen, LayoutGrid, ListChecks, Settings as SettingsIcon, SlidersHorizontal, Upload, Users } from 'lucide-react'
import { NavLink } from 'react-router-dom'
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

export function Sidebar() {
  const { openDialog, hasPendingBatch } = useUploadDialog()

  return (
    // The rail reserves a fixed 64px in the layout so the main content
    // never reflows; the actual panel is absolutely positioned over it and
    // only grows to full width on hover, so expanding never shifts anything
    // to its right.
    <div className="w-16 shrink-0 relative group">
      <div
        className="absolute inset-y-0 left-0 z-30 w-16 group-hover:w-56 bg-sidebar text-muted flex flex-col p-3.5
          border-r border-border overflow-hidden transition-[width] duration-200 ease-out"
      >
        {/* Labels have no opacity/visibility transition of their own - they're
            plain whitespace-nowrap text that the rail's overflow-hidden
            clips while collapsed and reveals as the rail's width animates
            open. A separately-timed opacity fade here would show the text
            before the rail finished widening, making it look like the icon
            and label were jumping around independently of the expansion. */}
        <NavLink to="/" end className="flex items-center gap-2.5 px-2 pt-1.5 pb-5.5">
          <div className="w-6.5 h-6.5 rounded-md bg-accent shrink-0" />
          <div className="text-sm font-semibold font-display text-text leading-tight whitespace-nowrap">
            Expenditure
            <br />
            Tracker
          </div>
        </NavLink>

        <button
          onClick={openDialog}
          disabled={hasPendingBatch}
          title={
            hasPendingBatch
              ? 'Review the pending statement before uploading another'
              : 'Upload a bank statement PDF - or drag & drop one anywhere in the app, anytime'
          }
          className="flex items-center justify-start gap-1.5 px-2.5 py-2.5 rounded-lg text-sm font-semibold border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Upload size={15} className="shrink-0" />
          <span className="whitespace-nowrap">Upload Bank Statement</span>
        </button>
        {/* Fixed width (independent of the rail's own collapsed/expanded
            width) so this always wraps the same way - otherwise, while
            collapsed, it wraps word-by-word against the 64px rail and the
            (invisible but still laid-out) text balloons into many lines. */}
        <div className="w-[190px] mx-auto text-[11px] text-muted-2 text-center leading-snug mt-1.5 mb-3.5">
          or drag &amp; drop a PDF — anytime, anywhere in the app
        </div>

        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2.5 rounded-lg text-sm font-medium mb-0.5 ${
                isActive ? 'text-text bg-accent/12' : 'text-nav hover:bg-nav-hover'
              }`
            }
          >
            {item.icon}
            <span className="whitespace-nowrap">{item.label}</span>
          </NavLink>
        ))}

        <div className="flex-1" />
        <div className="text-[11px] text-muted-2 px-2 pt-2.5 border-t border-border leading-relaxed whitespace-nowrap">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-success mr-1.5 shrink-0" />
          <span>Local-only · no data leaves this device</span>
        </div>
      </div>
    </div>
  )
}
