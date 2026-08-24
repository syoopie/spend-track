import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { useAiStatus, useSettings } from './api/hooks'
import { NarrowWindowNotice } from './components/NarrowWindowNotice'
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
    <div className="flex flex-col h-screen w-full overflow-hidden">
      <NarrowWindowNotice />
      <div className="flex flex-1 min-h-0 w-full overflow-hidden">
        <Sidebar />
        {/* PendingReviewBanner sits in its own non-scrolling row above the
            scroll pane (DASH-6 in UI Review.dc.html) - it used to be the
            first child inside the SAME overflow-y-auto div as the page
            content, so a page's own sticky top-0 header would scroll up and
            sit on top of it, hiding the banner as soon as you scrolled. */}
        <div className="flex-1 flex flex-col min-w-0">
          <PendingReviewBanner />
          <div className="flex-1 overflow-y-auto min-h-0">
            <Outlet />
          </div>
        </div>
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
