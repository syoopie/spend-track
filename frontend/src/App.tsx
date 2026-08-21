import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { UploadProvider } from './components/UploadProvider'
import { Dashboard } from './pages/Dashboard'
import { Contacts } from './pages/Contacts'
import { Rules } from './pages/Rules'
import { DefaultRules } from './pages/DefaultRules'
import { Guide } from './pages/Guide'
import { Settings } from './pages/Settings'

function MainLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden">
      <Sidebar />
      <div className="flex-1 overflow-y-auto min-w-0">
        <Outlet />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <UploadProvider>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Navigate to="/" replace />} />
          <Route path="/contacts" element={<Contacts />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/default-rules" element={<DefaultRules />} />
          <Route path="/guide" element={<Guide />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </UploadProvider>
  )
}
