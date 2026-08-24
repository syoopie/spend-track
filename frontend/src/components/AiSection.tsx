import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTestAiSettings, useUpdateAiSettings } from '../api/hooks'
import type { AiProviderKind, AiSettingsUpdateRequest, Settings as SettingsType } from '../api/types'
import { Button } from './Button'
import { Card } from './Card'
import { Checkbox } from './Checkbox'
import { Input } from './Field'
import { Tabs } from './Tabs'

const PROVIDER_LABELS: Record<AiProviderKind, string> = {
  ollama: 'Local (Ollama)',
  openai_compatible: 'OpenAI-compatible',
  anthropic: 'Anthropic (Claude)',
}

export function AiSection({ settings }: { settings: SettingsType | undefined }) {
  const updateAi = useUpdateAiSettings()
  const testAi = useTestAiSettings()

  const [enabled, setEnabled] = useState(false)
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

  const isCloudProvider = provider !== 'ollama'
  const openaiKeySet = settings?.openai_api_key_set ?? false
  const anthropicKeySet = settings?.anthropic_api_key_set ?? false

  // "Configured" means the selected provider has enough to actually attempt
  // a call - the Save button stays disabled until this is true (SET-1 in
  // UI Review.dc.html: the checkbox used to auto-save on its own, and an
  // unconfigured provider left it checked while the server silently
  // rejected the change - "Enable AI" now only ever takes effect through
  // this same Save button as every other field on the card).
  const providerConfigured =
    provider === 'ollama'
      ? ollamaModel.trim() !== ''
      : provider === 'openai_compatible'
        ? openaiBaseUrl.trim() !== '' && openaiModel.trim() !== '' && (openaiKeySet || openaiKey.trim() !== '')
        : anthropicModel.trim() !== '' && (anthropicKeySet || anthropicKey.trim() !== '')
  const canSave = !enabled || (providerConfigured && (!isCloudProvider || privacyAck))

  function draftBody(): AiSettingsUpdateRequest {
    return {
      ai_enabled: enabled,
      ai_provider: provider,
      ollama_url: ollamaUrl,
      ollama_model: ollamaModel,
      openai_base_url: openaiBaseUrl,
      openai_model: openaiModel,
      openai_api_key: openaiKey || undefined,
      anthropic_model: anthropicModel,
      anthropic_api_key: anthropicKey || undefined,
    }
  }

  function handleSave() {
    updateAi.mutate(draftBody(), {
      onSuccess: () => {
        setOpenaiKey('')
        setAnthropicKey('')
      },
      // Roll the checkbox (and everything else) back to whatever the server
      // actually has - a failed save must never leave the card asserting
      // something the server doesn't agree with.
      onError: () => {
        if (!settings) return
        setEnabled(settings.ai_enabled)
        setProvider(settings.ai_provider)
        setOllamaUrl(settings.ollama_url)
        setOllamaModel(settings.ollama_model)
        setOpenaiBaseUrl(settings.openai_base_url)
        setOpenaiModel(settings.openai_model)
        setAnthropicModel(settings.anthropic_model)
      },
    })
  }

  function handleTest() {
    testAi.mutate(draftBody())
  }

  // Reset the last test result whenever the draft changes underneath it -
  // otherwise switching providers or editing a field after a successful
  // test would keep showing a "Connected" pill for a config that's no
  // longer what's on screen.
  useEffect(() => {
    testAi.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [provider, ollamaUrl, ollamaModel, openaiBaseUrl, openaiModel, openaiKey, anthropicModel, anthropicKey])

  const detectedModels = testAi.data?.reachable ? testAi.data.models : []

  return (
    <Card className="mb-4">
      <div className="text-md font-semibold font-display mb-1">AI</div>
      <div className="text-xs text-muted mb-3.5">
        Lets the app call out to a language model to help with things the built-in rule engine can't handle on its
        own. <strong className="text-text-2">Categorization is currently the only AI-powered feature</strong>:
        whatever the rule engine leaves in "Others" is sent to a model for a suggested category, label, and rule -
        automatically on every upload and Recategorize run, always shown for review before it's relied on.
      </div>

      <label className="flex items-center gap-2 text-md text-text cursor-pointer w-fit">
        <Checkbox checked={enabled} onChange={setEnabled} />
        Enable AI
      </label>

      {/* Connection details only matter once AI is actually on. Toggling this
          no longer saves anything by itself - it only reveals the fields
          below, and Save is what persists ai_enabled along with them. */}
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
              {/* SET-4: the privacy warning above asserted what leaves the
                  device without ever showing it. This is a static, honest
                  example - not live data - of the exact shape of one request. */}
              <details className="mb-2.5">
                <summary
                  className="text-2xs cursor-pointer select-none"
                  style={{ color: 'var(--color-warning-text)' }}
                >
                  What exactly gets sent?
                </summary>
                <div className="mt-1.5 rounded-md bg-card/60 border border-border p-2 font-mono text-2xs text-text-2 whitespace-pre overflow-x-auto">
                  {'{\n  "description": "NETS QR PAYMENT KOPITIAM BLK 123",\n  "amount": -4.50\n}'}
                </div>
                <div className="text-2xs mt-1.5" style={{ color: 'var(--color-warning-text)' }}>
                  One request per uncategorized transaction — just its description and amount, nothing else (no
                  account numbers, no other transactions).
                </div>
              </details>
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
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={updateAi.isPending || !canSave}
              title={!canSave && enabled ? 'Fill in the required fields above (and the privacy checkbox) before saving' : undefined}
            >
              Save
            </Button>
            {/* Posts the draft above to the backend without persisting it
                (SET-4) - the old flow required Save before a key could ever
                be checked at all. */}
            <Button size="sm" onClick={handleTest} disabled={testAi.isPending}>
              Test Connection
            </Button>
            {testAi.isPending ? (
              <span className="text-xs text-muted flex items-center gap-1.5">
                <Loader2 size={13} className="animate-spin" /> Testing…
              </span>
            ) : testAi.data?.reachable ? (
              <span className="text-xs text-success flex items-center gap-1.5">
                <CheckCircle2 size={13} /> Connected
                {testAi.data.models.length > 0 && ` · ${testAi.data.models.length} model(s) available`}
              </span>
            ) : testAi.data ? (
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--color-danger-text)' }}>
                <XCircle size={13} /> Unreachable{testAi.data.error ? ` · ${testAi.data.error}` : ''}
              </span>
            ) : testAi.isError ? (
              <span className="text-xs flex items-center gap-1.5" style={{ color: 'var(--color-danger-text)' }}>
                <XCircle size={13} /> Couldn't test that connection.
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
