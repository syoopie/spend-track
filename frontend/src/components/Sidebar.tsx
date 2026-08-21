import { LayoutGrid, ListChecks, Settings as SettingsIcon, SlidersHorizontal, Upload, Users } from 'lucide-react'
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
    to: '/settings',
    label: 'Settings',
    icon: <SettingsIcon size={16} className="shrink-0" />,
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
        <Upload size={15} className="shrink-0" />
        Upload Statement
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
