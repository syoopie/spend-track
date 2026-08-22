import { CheckCircle2, Loader2, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useAiStatus,
  useDeleteAllContacts,
  useDeleteAllRules,
  useDeleteAllTransactions,
  useRelocateDb,
  useResetDb,
  useSettings,
  useUpdateAiSettings,
} from '../api/hooks'
import { Checkbox } from '../components/Checkbox'
import { Modal } from '../components/Modal'
import { Tabs } from '../components/Tabs'
import { fmtBytes } from '../lib/format'
import { ACCENT_PRESETS, DEFAULT_ACCENT, loadStoredAccentColor, resetAccentColor, saveAccentColor } from '../lib/accentColor'
import type { AiProviderKind, Settings as SettingsType } from '../api/types'

const PROVIDER_LABELS: Record<AiProviderKind, string> = {
  ollama: 'Local (Ollama)',
  openai_compatible: 'OpenAI-compatible',
  anthropic: 'Anthropic (Claude)',
}

// How long to wait after the last toggle before persisting it - avoids
// firing a request per click if the user flips the checkbox a few times in
// a row (e.g. double-clicking).
const ENABLE_TOGGLE_DEBOUNCE_MS = 600

function AiSection({ settings }: { settings: SettingsType | undefined }) {
  const updateAi = useUpdateAiSettings()
  const toggleAi = useUpdateAiSettings()

  const [enabled, setEnabled] = useState(false)
  const [toggleNotice, setToggleNotice] = useState<{ kind: 'success' | 'error'; text: string } | null>(null)
  const toggleTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
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

  // Cleanup pending timers on unmount so a debounced save or a fading
  // notice doesn't fire setState after the section is gone.
  useEffect(() => {
    return () => {
      if (toggleTimer.current) clearTimeout(toggleTimer.current)
      if (noticeTimer.current) clearTimeout(noticeTimer.current)
    }
  }, [])

  function showToggleNotice(kind: 'success' | 'error', text: string) {
    setToggleNotice({ kind, text })
    if (noticeTimer.current) clearTimeout(noticeTimer.current)
    noticeTimer.current = setTimeout(() => setToggleNotice(null), kind === 'success' ? 2500 : 6000)
  }

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
          onSuccess: () => showToggleNotice('success', next ? 'AI categorization enabled.' : 'AI categorization disabled.'),
          onError: (err) =>
            showToggleNotice(
              'error',
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
    <div className="bg-card border border-border rounded-xl p-5 mb-4">
      <div className="text-[13px] font-semibold mb-1">AI Categorization</div>
      <div className="text-xs text-muted mb-3.5">
        Whatever the rule engine can't resolve is sent to a model for a suggested category, label, and rule -
        automatically on every upload and Recategorize run, always shown for review before it's relied on.
      </div>

      <label className="flex items-center gap-2 text-[13px] text-text cursor-pointer w-fit">
        <Checkbox checked={enabled} onChange={handleToggleEnabled} />
        Enable AI categorization
      </label>
      {toggleNotice && (
        <div
          className={`text-[12px] mt-1.5 ${toggleNotice.kind === 'success' ? 'text-success' : ''}`}
          style={toggleNotice.kind === 'error' ? { color: 'oklch(70% 0.18 25)' } : undefined}
        >
          {toggleNotice.text}
        </div>
      )}

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
                <input
                  value={ollamaUrl}
                  onChange={(e) => setOllamaUrl(e.target.value)}
                  placeholder="http://localhost:11434"
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <input
                  value={ollamaModel}
                  onChange={(e) => setOllamaModel(e.target.value)}
                  placeholder="llama3.1"
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
                {detectedModels.length > 0 && (
                  <div className="text-[11px] text-muted mt-1.5 flex flex-wrap gap-1.5">
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
                <input
                  value={openaiBaseUrl}
                  onChange={(e) => setOpenaiBaseUrl(e.target.value)}
                  placeholder="https://api.openai.com/v1"
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
                <div className="text-[11px] text-muted mt-1">
                  Also works with OpenRouter, Groq, together.ai, a self-hosted LiteLLM proxy, or anything else
                  exposing the OpenAI chat-completions API - including Codex-family models, just point this at
                  OpenAI.
                </div>
              </div>
              <div>
                <div className="text-xs text-muted mb-1">API key</div>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={openaiKeySet ? `Set · sk-…${settings?.openai_api_key_last4}` : 'sk-...'}
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <input
                  value={openaiModel}
                  onChange={(e) => setOpenaiModel(e.target.value)}
                  placeholder="gpt-4o-mini"
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
                {detectedModels.length > 0 && (
                  <div className="text-[11px] text-muted mt-1.5 flex flex-wrap gap-1.5 max-w-full overflow-hidden">
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
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder={anthropicKeySet ? `Set · sk-ant-…${settings?.anthropic_api_key_last4}` : 'sk-ant-...'}
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
              </div>
              <div>
                <div className="text-xs text-muted mb-1">Model</div>
                <input
                  value={anthropicModel}
                  onChange={(e) => setAnthropicModel(e.target.value)}
                  placeholder="claude-sonnet-5"
                  className="w-full box-border px-3 py-2 rounded-lg border border-border bg-input text-text text-[13px] font-mono"
                />
              </div>
            </div>
          )}

          {isCloudProvider && (
            <div
              className="rounded-lg px-3.5 py-3 mt-3.5"
              style={{ background: 'oklch(24% 0.05 70)', border: '1px solid oklch(40% 0.08 70)' }}
            >
              <div className="text-[12px] mb-2" style={{ color: 'oklch(85% 0.1 70)' }}>
                Transaction descriptions and amounts will be sent to {PROVIDER_LABELS[provider]}'s servers when
                categorizing. This app is local-first by design — only continue if you're comfortable with that.
              </div>
              <label
                className="flex items-center gap-2 text-[12px] cursor-pointer w-fit"
                style={{ color: 'oklch(85% 0.1 70)' }}
              >
                <Checkbox checked={privacyAck} onChange={setPrivacyAck} />
                I understand transaction data will leave this device
              </label>
            </div>
          )}

          <div className="flex items-center gap-3 mt-4">
            <button
              onClick={handleSave}
              disabled={updateAi.isPending || !canSave}
              className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
            >
              Save
            </button>
            <button
              onClick={() => statusQ.refetch()}
              disabled={statusQ.isFetching || !statusAppliesToThisTab}
              className="text-[12px] px-3 py-2 rounded-lg border border-border bg-input text-text cursor-pointer disabled:opacity-60"
            >
              Recheck connection
            </button>
            {!statusAppliesToThisTab ? (
              <span className="text-[12px] text-muted">Save to test this provider's connection.</span>
            ) : statusQ.isFetching ? (
              <span className="text-[12px] text-muted flex items-center gap-1.5">
                <Loader2 size={13} className="animate-spin" /> Checking…
              </span>
            ) : statusQ.data?.reachable ? (
              <span className="text-[12px] text-success flex items-center gap-1.5">
                <CheckCircle2 size={13} /> Connected
                {statusQ.data.models.length > 0 && ` · ${statusQ.data.models.length} model(s) available`}
              </span>
            ) : statusQ.data ? (
              <span className="text-[12px] flex items-center gap-1.5" style={{ color: 'oklch(70% 0.18 25)' }}>
                <XCircle size={13} /> Unreachable{statusQ.data.error ? ` · ${statusQ.data.error}` : ''}
              </span>
            ) : null}
          </div>
          {updateAi.isError && (
            <div className="text-[12px] text-danger-text mt-2.5">
              {updateAi.error instanceof Error ? updateAi.error.message : 'Could not save AI settings.'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AppearanceSection() {
  const [accent, setAccent] = useState(loadStoredAccentColor())

  function pick(hex: string) {
    setAccent(hex)
    saveAccentColor(hex)
  }

  function reset() {
    setAccent(DEFAULT_ACCENT)
    resetAccentColor()
  }

  return (
    <div className="bg-card border border-border rounded-xl p-5 mb-4">
      <div className="text-[13px] font-semibold mb-1">Appearance</div>
      <div className="text-xs text-muted mb-3.5">Choose the accent color used for buttons, links, and highlights.</div>
      <div className="flex items-center gap-2.5 flex-wrap">
        {ACCENT_PRESETS.map((p) => (
          <button
            key={p.hex}
            onClick={() => pick(p.hex)}
            title={p.name}
            className="w-7 h-7 rounded-full cursor-pointer"
            style={{
              background: p.hex,
              outline: accent.toLowerCase() === p.hex.toLowerCase() ? '2px solid var(--color-text)' : 'none',
              outlineOffset: 2,
              border: 'none',
            }}
          />
        ))}
        <label
          title="Custom color"
          className="relative w-7 h-7 rounded-full cursor-pointer border border-border overflow-hidden flex items-center justify-center"
          style={{
            background: ACCENT_PRESETS.some((p) => p.hex.toLowerCase() === accent.toLowerCase())
              ? 'conic-gradient(from 0deg, #e35fd0, #a78bfa, #5b9dff, #2dd4bf, #4ade80, #fbbf24, #fb923c, #f87171, #e35fd0)'
              : accent,
          }}
        >
          <input
            type="color"
            value={accent}
            onChange={(e) => pick(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer"
          />
        </label>
        <button
          onClick={reset}
          className="text-[12px] text-muted hover:text-text cursor-pointer border-none bg-transparent ml-1"
        >
          Reset to default
        </button>
      </div>
    </div>
  )
}

function RelocateModal({ dbSize, onClose }: { dbSize: string; onClose: () => void }) {
  const relocate = useRelocateDb()
  const [newPath, setNewPath] = useState('')

  async function handleMigrate() {
    if (!newPath.trim()) return
    await relocate.mutateAsync(newPath.trim())
    onClose()
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5">Change Database Path</div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        This migrates a <strong className="text-text">{dbSize}</strong> database file to the new location. Active
        connections will be closed during the move, then reopened at the new path.
      </div>
      <div className="text-xs text-muted mb-1">New location</div>
      <input
        value={newPath}
        onChange={(e) => setNewPath(e.target.value)}
        placeholder="/Users/you/Documents/sg-tracker-data.db"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      {relocate.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not relocate the database. Check the path.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleMigrate}
          disabled={relocate.isPending || !newPath.trim()}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
        >
          Migrate Database
        </button>
      </div>
    </Modal>
  )
}

function ScopedDeleteModal({
  title,
  description,
  confirmLabel,
  mutation,
  onClose,
}: {
  title: string
  description: string
  confirmLabel: string
  mutation: ReturnType<typeof useDeleteAllRules> | ReturnType<typeof useDeleteAllContacts> | ReturnType<typeof useDeleteAllTransactions>
  onClose: () => void
}) {
  const [confirm, setConfirm] = useState('')
  const canDelete = confirm === 'DELETE'

  async function handleDelete() {
    if (!canDelete) return
    try {
      await mutation.mutateAsync(confirm)
      onClose()
    } catch {
      // swallow - mutation.isError below renders the failure, modal stays open so the user can retry
    }
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5" style={{ color: 'oklch(72% 0.16 25)' }}>
        {title}
      </div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        {description} Type <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <input
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder="DELETE"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      {mutation.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not complete the deletion. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleDelete}
          disabled={!canDelete || mutation.isPending}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer"
          style={{
            background: canDelete ? 'var(--color-danger)' : 'var(--color-border)',
            color: canDelete ? 'var(--color-danger-fg)' : 'var(--color-muted-2)',
            cursor: canDelete ? 'pointer' : 'not-allowed',
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

function NuclearResetModal({ onClose }: { onClose: () => void }) {
  const reset = useResetDb()
  const navigate = useNavigate()
  const [confirm, setConfirm] = useState('')
  const canReset = confirm === 'DELETE'

  async function handleReset() {
    if (!canReset) return
    try {
      await reset.mutateAsync(confirm)
      onClose()
      navigate('/')
    } catch {
      // swallow - reset.isError below renders the failure, modal stays open so the user can retry
    }
  }

  return (
    <Modal onClose={onClose} width={420}>
      <div className="text-base font-bold mb-2.5" style={{ color: 'oklch(72% 0.16 25)' }}>
        Nuclear Reset
      </div>
      <div className="text-[13px] text-muted leading-relaxed mb-4">
        This permanently deletes all accounts, transactions, contacts and rules. Type{' '}
        <strong className="font-mono text-text">DELETE</strong> to confirm.
      </div>
      <input
        value={confirm}
        onChange={(e) => setConfirm(e.target.value)}
        placeholder="DELETE"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] font-mono mb-4.5"
      />
      {reset.isError && (
        <div className="text-[12px] text-danger-text mb-3">Could not complete the reset. Please try again.</div>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          onClick={onClose}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={handleReset}
          disabled={!canReset || reset.isPending}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer"
          style={{
            background: canReset ? 'var(--color-danger)' : 'var(--color-border)',
            color: canReset ? 'var(--color-danger-fg)' : 'var(--color-muted-2)',
            cursor: canReset ? 'pointer' : 'not-allowed',
          }}
        >
          Purge Everything
        </button>
      </div>
    </Modal>
  )
}

type DeleteScope = 'rules' | 'contacts' | 'transactions' | null

export function Settings() {
  const settingsQ = useSettings()
  const [relocateOpen, setRelocateOpen] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  const [deleteScope, setDeleteScope] = useState<DeleteScope>(null)

  const deleteRules = useDeleteAllRules()
  const deleteContacts = useDeleteAllContacts()
  const deleteTransactions = useDeleteAllTransactions()

  const dbSize = settingsQ.data ? fmtBytes(settingsQ.data.size_bytes) : '—'

  return (
    <div className="px-9 pt-7 pb-15 max-w-2xl">
      <div className="text-[22px] font-bold font-display mb-5">Settings &amp; Storage</div>

      <AppearanceSection />

      <AiSection settings={settingsQ.data} />

      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <div className="text-[13px] font-semibold mb-1">Region</div>
        <div className="text-xs text-muted mb-3.5">
          Statement parsing, currency formatting, and the default rule bank are all specific to this region.
        </div>
        <div className="flex gap-6 flex-wrap">
          <div>
            <div className="text-xs text-muted">Country</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.country_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Currency</div>
            <div className="text-[13px] font-mono">
              {settingsQ.data ? `${settingsQ.data.currency_code} (${settingsQ.data.currency_symbol})` : '—'}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted">Transfer scheme</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.transfer_scheme_name ?? '—'}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Supported banks</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.supported_banks.join(', ') ?? '—'}</div>
          </div>
        </div>
      </div>

      <div className="bg-card border border-border rounded-xl p-5 mb-4">
        <div className="text-[13px] font-semibold mb-3.5">Database</div>
        <div className="text-xs text-muted mb-0.5">Path</div>
        <div className="text-[13px] font-mono mb-3 break-all">{settingsQ.data?.db_path ?? '—'}</div>
        <div className="flex gap-6 mb-4">
          <div>
            <div className="text-xs text-muted">Size</div>
            <div className="text-[13px] font-mono">{dbSize}</div>
          </div>
          <div>
            <div className="text-xs text-muted">Schema version</div>
            <div className="text-[13px] font-mono">{settingsQ.data?.schema_version ?? '—'}</div>
          </div>
        </div>
        <button
          onClick={() => setRelocateOpen(true)}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Change Database Path
        </button>
      </div>

      <div className="bg-card rounded-xl p-5" style={{ border: '1px solid oklch(40% 0.08 25)' }}>
        <div className="text-[13px] font-semibold mb-1.5" style={{ color: 'oklch(72% 0.16 25)' }}>
          Danger Zone
        </div>
        <div className="text-[13px] text-muted mb-3.5 leading-relaxed">
          Selectively clear one part of the local database, or permanently delete everything. None of this can be
          undone.
        </div>
        <div className="flex gap-2.5 flex-wrap mb-4">
          <button
            onClick={() => setDeleteScope('rules')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Rules
          </button>
          <button
            onClick={() => setDeleteScope('contacts')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Contacts
          </button>
          <button
            onClick={() => setDeleteScope('transactions')}
            className="text-[13px] font-semibold px-4 py-2.5 rounded-lg cursor-pointer bg-input"
            style={{ border: '1px solid oklch(45% 0.15 25)', color: 'oklch(70% 0.18 25)' }}
          >
            Delete All Transactions
          </button>
        </div>
        <div className="h-px bg-border/70 mb-4" />
        <button
          onClick={() => setResetOpen(true)}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none cursor-pointer text-white"
          style={{ background: 'oklch(55% 0.19 25)' }}
        >
          Nuclear Reset
        </button>
      </div>

      {relocateOpen && <RelocateModal dbSize={dbSize} onClose={() => setRelocateOpen(false)} />}
      {resetOpen && <NuclearResetModal onClose={() => setResetOpen(false)} />}
      {deleteScope === 'rules' && (
        <ScopedDeleteModal
          title="Delete All Rules"
          description="This permanently deletes every rule you've created. Built-in default rules are not affected."
          confirmLabel="Delete Rules"
          mutation={deleteRules}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'contacts' && (
        <ScopedDeleteModal
          title="Delete All Contacts"
          description="This permanently deletes every contact and their linked identifiers."
          confirmLabel="Delete Contacts"
          mutation={deleteContacts}
          onClose={() => setDeleteScope(null)}
        />
      )}
      {deleteScope === 'transactions' && (
        <ScopedDeleteModal
          title="Delete All Transactions"
          description="This permanently deletes every committed transaction. Accounts themselves are kept, so you can re-upload statements without losing account setup."
          confirmLabel="Delete Transactions"
          mutation={deleteTransactions}
          onClose={() => setDeleteScope(null)}
        />
      )}
    </div>
  )
}
