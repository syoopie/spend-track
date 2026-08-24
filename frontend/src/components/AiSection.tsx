import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAiStatus, useUpdateAiSettings } from '../api/hooks'
import type { AiProviderKind, Settings as SettingsType } from '../api/types'
import { Button } from './Button'
import { Card } from './Card'
import { Checkbox } from './Checkbox'
import { Input } from './Field'
import { Tabs } from './Tabs'
import { useToast } from './Toast'

const PROVIDER_LABELS: Record<AiProviderKind, string> = {
  ollama: 'Local (Ollama)',
  openai_compatible: 'OpenAI-compatible',
  anthropic: 'Anthropic (Claude)',
}

// How long to wait after the last toggle before persisting it - avoids
// firing a request per click if the user flips the checkbox a few times in
// a row (e.g. double-clicking).
const ENABLE_TOGGLE_DEBOUNCE_MS = 600

export function AiSection({ settings }: { settings: SettingsType | undefined }) {
  const updateAi = useUpdateAiSettings()
  const toggleAi = useUpdateAiSettings()
  const toast = useToast()

  const [enabled, setEnabled] = useState(false)
  const toggleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [provider, setProvider] = useState<AiProviderKind>('ollama')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [ollamaModel, setOllamaModel] = useState('')
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('')
  const [openaiModel, setOpenaiModel] = useState('')
  const [openaiKey, setOpenaiKey] = useState('')
  const [anthropicModel, setAnthropicModel] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [privacyAck, setPrivacyAck] = useState(false)
  const [initialized, setInitialized] = useState(false)
  // Only worth checking reachability once the connection fields are
  // actually visible (i.e. AI is on) - see the `enabled &&` gate below.
  const statusQ = useAiStatus(enabled)

  // Seed local editable state from the server once, the first time settings
  // load - not on every refetch, or the user's in-progress edits would keep
  // getting clobbered by background refetches of the same query.
  useEffect(() => {
    if (initialized || !settings) return
    setEnabled(settings.ai_enabled)
    setProvider(settings.ai_provider)
    setOllamaUrl(settings.ollama_url)
    setOllamaModel(settings.ollama_model)
    setOpenaiBaseUrl(settings.openai_base_url)
    setOpenaiModel(settings.openai_model)
    setAnthropicModel(settings.anthropic_model)
    setInitialized(true)
  }, [settings, initialized])

  // Cleanup the pending debounce timer on unmount so it doesn't fire a
  // mutation after the section is gone.
  useEffect(() => {
    return () => {
      if (toggleTimer.current) clearTimeout(toggleTimer.current)
    }
  }, [])

  // "Enable AI" is implicitly saved on its own, debounced, the moment it's
  // toggled - unlike every other field here, which only persists via the
  // explicit Save button below. If nothing's configured for the current
  // provider yet, the auto-save 400s (AI_PROVIDER_NOT_CONFIGURED); the
  // checkbox stays checked anyway so the now-visible fields below can be
  // filled in, and the full Save button (which also sends ai_enabled) picks
  // up the slack once they are.
  function handleToggleEnabled(next: boolean) {
    setEnabled(next)
    if (toggleTimer.current) clearTimeout(toggleTimer.current)
    toggleTimer.current = setTimeout(() => {
      toggleAi.mutate(
        { ai_enabled: next },
        {
          onSuccess: () => toast.success(next ? 'AI enabled.' : 'AI disabled.'),
          onError: (err) =>
            toast.error(
              next
                ? `Couldn't enable AI yet: ${err instanceof Error ? err.message : 'configure a provider below, then click Save.'}`
                : "Couldn't save that change. Please try again.",
            ),
        },
      )
    }, ENABLE_TOGGLE_DEBOUNCE_MS)
  }

  const isCloudProvider = provider !== 'ollama'
  const canSave = !isCloudProvider || !enabled || privacyAck
  const openaiKeySet = settings?.openai_api_key_set ?? false
  const anthropicKeySet = settings?.anthropic_api_key_set ?? false
  // /settings/ai/status always checks whatever provider is currently SAVED,
  // not whichever tab is being edited - without this, switching tabs before
  // saving would show the previous provider's reachability under the new
  // one's fields, which reads as "this untested config is unreachable".
  const statusAppliesToThisTab = provider === settings?.ai_provider
  const detectedModels = statusAppliesToThisTab ? (statusQ.data?.models ?? []) : []

  function handleSave() {
    updateAi.mutate({
      ai_enabled: enabled,
      ai_provider: provider,
      ollama_url: ollamaUrl,
      ollama_model: ollamaModel,
      openai_base_url: openaiBaseUrl,
      openai_model: openaiModel,
      openai_api_key: openaiKey || undefined,
      anthropic_model: anthropicModel,
      anthropic_api_key: anthropicKey || undefined,
    })
    setOpenaiKey('')
    setAnthropicKey('')
  }

  return (
    <Card className="mb-4">
      <div className="text-md font-semibold mb-1">AI</div>
      <div className="text-xs text-muted mb-3.5">
        Lets the app call out to a language model to help with things the built-in rule engine can't handle on its
        own. <strong className="text-text-2">Categorization is currently the only AI-powered feature</strong>:
        whatever the rule engine leaves in "Others" is sent to a model for a suggested category, label, and rule -
        automatically on every upload and Recategorize run, always shown for review before it's relied on.
      </div>

      <label className="flex items-center gap-2 text-md text-text cursor-pointer w-fit">
        <Checkbox checked={enabled} onChange={handleToggleEnabled} />
        Enable AI
      </label>

      {/* Connection details only matter once AI is actually on. */}
      {enabled && (
        <div className="mt-4">
          <Tabs
            tabs={(Object.keys(PROVIDER_LABELS) as AiProviderKind[]).map((k) => ({ key: k, label: PROVIDER_LABELS[k] }))}
            active={provider}
            onChange={setProvider}
          />

          {provider === 'ollama' && (
            <div className="flex flex-col gap-3 mb-1">
              <div>
                <div className="text-xs text-muted mb-1">Ollama URL</div>
                <Input mono value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} placeholder="http://localhost:11434" />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <Input mono value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} placeholder="llama3.1" />
                {detectedModels.length > 0 && (
                  <div className="text-2xs text-muted mt-1.5 flex flex-wrap gap-1.5">
                    Detected:
                    {detectedModels.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setOllamaModel(m)}
                        className="font-mono text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {provider === 'openai_compatible' && (
            <div className="flex flex-col gap-3 mb-1">
              <div>
                <div className="text-xs text-muted mb-1">Base URL</div>
                <Input mono value={openaiBaseUrl} onChange={(e) => setOpenaiBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
                <div className="text-2xs text-muted mt-1">
                  Also works with OpenRouter, Groq, together.ai, a self-hosted LiteLLM proxy, or anything else
                  exposing the OpenAI chat-completions API - including Codex-family models, just point this at
                  OpenAI.
                </div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">API key</div>
                <Input
                  mono
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={openaiKeySet ? `Set · sk-…${settings?.openai_api_key_last4}` : 'sk-...'}
                />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <Input mono value={openaiModel} onChange={(e) => setOpenaiModel(e.target.value)} placeholder="gpt-4o-mini" />
                {detectedModels.length > 0 && (
                  <div className="text-2xs text-muted mt-1.5 flex flex-wrap gap-1.5 max-w-full overflow-hidden">
                    Detected:
                    {detectedModels.slice(0, 8).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setOpenaiModel(m)}
                        className="font-mono text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {provider === 'anthropic' && (
            <div className="flex flex-col gap-3 mb-1">
              <div>
                <div className="text-xs text-muted mb-1">API key</div>
                <Input
                  mono
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder={anthropicKeySet ? `Set · sk-ant-…${settings?.anthropic_api_key_last4}` : 'sk-ant-...'}
                />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <Input mono value={anthropicModel} onChange={(e) => setAnthropicModel(e.target.value)} placeholder="claude-sonnet-5" />
              </div>
            </div>
          )}

          {isCloudProvider && (
            <div
              className="rounded-lg px-3.5 py-3 mt-3.5"
              style={{ background: 'var(--color-warning-surface)', border: '1px solid var(--color-warning-surface-border)' }}
            >
              <div className="text-xs mb-2" style={{ color: 'var(--color-warning-text)' }}>
                Transaction descriptions and amounts will be sent to {PROVIDER_LABELS[provider]}'s servers when
                categorizing. This app is local-first by design — only continue if you're comfortable with that.
              </div>
              <label
                className="flex items-center gap-2 text-xs cursor-pointer w-fit"
                style={{ color: 'var(--color-warning-text)' }}
              >
                <Checkbox checked={privacyAck} onChange={setPrivacyAck} />
                I understand transaction data will leave this device
              </label>
            </div>
          )}

          <div className="flex items-center gap-3 mt-4">
            <Button variant="primary" onClick={handleSave} disabled={updateAi.isPending || !canSave}>
              Save
            </Button>
            <Button size="sm" onClick={() => statusQ.refetch()} disabled={statusQ.isFetching || !statusAppliesToThisTab}>
              Recheck connection
            </Button>
            {!statusAppliesToThisTab ? (
              <span className="text-xs text-muted">Save to test this provider's connection.</span>
            ) : statusQ.isFetching ? (
              <span className="text-xs text-muted flex items-center gap-1.5">
                <Loader2 size={13} className="animate-spin" /> Checking…
              </span>
            ) : statusQ.data?.reachable ? (
              <span className="text-xs text-success flex items-center gap-1.5">
                <CheckCircle2 size={13} /> Connected
                {statusQ.data.models.length > 0 && ` · ${statusQ.data.models.length} model(s) available`}
              </span>
            ) : statusQ.data ? (
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--color-danger-text)' }}>
                <XCircle size={13} /> Unreachable{statusQ.data.error ? ` · ${statusQ.data.error}` : ''}
              </span>
            ) : null}
          </div>
          {updateAi.isError && (
            <div className="text-xs text-danger-text mt-2.5">
              {updateAi.error instanceof Error ? updateAi.error.message : 'Could not save AI settings.'}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
