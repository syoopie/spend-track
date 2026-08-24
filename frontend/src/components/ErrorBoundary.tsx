import { Component, type ErrorInfo, type ReactNode } from 'react'
import { ErrorState } from './EmptyState'

// Wraps the router (see main.tsx) so a render error in one screen shows a
// recoverable full-page ErrorState instead of a blank white tab - X-4 in
// UI Review.dc.html: before this there was no error boundary at all. Class
// component because getDerivedStateFromError/componentDidCatch have no hook
// equivalent.
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <ErrorState
            title="Something broke"
            description="This screen hit an unexpected error. Reloading usually clears it."
            onRetry={() => {
              this.setState({ error: null })
              window.location.reload()
            }}
          />
        </div>
      )
    }
    return this.props.children
  }
}
