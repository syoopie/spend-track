import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.tsx'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ToastProvider } from './components/Toast'
import { applyAccentColor, loadStoredAccentColor } from './lib/accentColor'

applyAccentColor(loadStoredAccentColor())

const queryClient = new QueryClient({
  defaultOptions: {
    // A fresh query still refetches on the first mount ever (route load,
    // full page reload); staleTime only skips the redundant refetch when
    // navigating back to a screen whose data hasn't gone stale yet -
    // DASH-1 in UI Review.dc.html. Paired with each list query's own
    // placeholderData: keepPreviousData for the case staleTime doesn't
    // cover: the query KEY itself changing (a new date range/account),
    // which staleTime has no say over.
    queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 30_000 },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
)
