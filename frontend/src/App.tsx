import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAiStatus, useSettings } from './api/hooks'
import { PendingReviewBanner } from './components/PendingReviewBanner'
import { Sidebar } from './components/Sidebar'
import { UploadProvider } from './components/UploadProvider'
import { Dashboard } from './pages/Dashboard'
import { Contacts } from './pages/Contacts'
import { Rules } from './pages/Rules'
import { DefaultRules } from './pages/DefaultRules'
import { Guide } from './pages/Guide'
import { Settings } from './pages/Settings'

// Warms the AI reachability check as soon as the app loads (if AI is
// enabled) so Settings/staging/recategorize screens don't each have to
// trigger the first check themselves - no UI of its own, it just primes
// the ['ai-status'] query cache other screens read from.
function AiStatusWarmup() {
  const settingsQ = useSettings()
  useAiStatus(!!settingsQ.data?.ai_enabled)
  return null
}

function MainLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden">
      <Sidebar />
      <div className="flex-1 overflow-y-auto min-w-0">
        <PendingReviewBanner />
        <Outlet />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <UploadProvider>
      <AiStatusWarmup />
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
