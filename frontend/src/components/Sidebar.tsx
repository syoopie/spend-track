import { ListChecks } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useUploadDialog } from './UploadProvider'

const NAV_ITEMS = [
  {
    to: '/',
    label: 'Dashboard',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
        <rect x="1" y="1" width="6" height="6" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <rect x="9" y="1" width="6" height="6" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <rect x="1" y="9" width="6" height="6" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <rect x="9" y="9" width="6" height="6" fill="none" stroke="currentColor" strokeWidth="1.3" />
      </svg>
    ),
  },
  {
    to: '/contacts',
    label: 'Contacts',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
        <circle cx="8" cy="5" r="3" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <rect x="2.5" y="10" width="11" height="5" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
      </svg>
    ),
  },
  {
    to: '/rules',
    label: 'Rules',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
        <line x1="5" y1="3" x2="15" y2="3" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="2" cy="3" r="1.4" fill="currentColor" />
        <line x1="1" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="14" cy="8" r="1.4" fill="currentColor" />
        <line x1="5" y1="13" x2="15" y2="13" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="2" cy="13" r="1.4" fill="currentColor" />
      </svg>
    ),
  },
  {
    to: '/default-rules',
    label: 'Default Rules',
    icon: <ListChecks size={16} className="shrink-0" />,
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" className="shrink-0">
        <circle cx="8" cy="8" r="4" fill="none" stroke="currentColor" strokeWidth="1.3" />
        <line x1="8" y1="0.5" x2="8" y2="2.3" stroke="currentColor" strokeWidth="1.3" />
        <line x1="8" y1="13.7" x2="8" y2="15.5" stroke="currentColor" strokeWidth="1.3" />
        <line x1="0.5" y1="8" x2="2.3" y2="8" stroke="currentColor" strokeWidth="1.3" />
        <line x1="13.7" y1="8" x2="15.5" y2="8" stroke="currentColor" strokeWidth="1.3" />
      </svg>
    ),
  },
]

export function Sidebar() {
  const { openDialog, hasPendingBatch } = useUploadDialog()

  return (
    <div className="w-56 shrink-0 bg-sidebar text-muted flex flex-col p-3.5 border-r border-border">
      <NavLink to="/" end className="flex items-center gap-2.5 px-2 pt-1.5 pb-5.5">
        <div className="w-6.5 h-6.5 rounded-md bg-accent shrink-0" />
        <div className="text-sm font-semibold text-text leading-tight">
          Expenditure
          <br />
          Tracker
        </div>
      </NavLink>

      <button
        onClick={openDialog}
        disabled={hasPendingBatch}
        title={hasPendingBatch ? 'Review the pending statement before uploading another' : undefined}
        className="flex items-center justify-center gap-1.5 px-2.5 py-2.5 rounded-lg text-sm font-semibold mb-3.5 border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        + Upload Statement
      </button>

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
          {item.label}
        </NavLink>
      ))}

      <div className="flex-1" />
      <div className="text-[11px] text-muted-2 px-2 pt-2.5 border-t border-border leading-relaxed">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-success mr-1.5" />
        Local-only · no data leaves this device
      </div>
    </div>
  )
}
