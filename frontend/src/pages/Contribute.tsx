import {
  AlertTriangle,
  FileUp,
  ExternalLink,
  HeartHandshake,
  Info,
  Lock,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError } from '../api/client'
import { useSanitizeStatement, useSettings } from '../api/hooks'
import type { SanitizeParseStatus, SanitizeResult } from '../api/types'
import { Button } from '../components/Button'
import { Card } from '../components/Card'
import { Checkbox } from '../components/Checkbox'
import { ErrorState } from '../components/EmptyState'
import { Field, Input } from '../components/Field'
import { Modal } from '../components/Modal'
import { PageShell } from '../components/PageShell'
import { useUploadDialog } from '../components/UploadProvider'

const GITHUB_NEW_ISSUE = 'https://github.com/syoopie/spend-track/issues/new'

// A result on the review step always carries a file. The two reasons it
// might not - a scan with no text, and an outright failure - are their own
// steps, so nothing downstream of here has to re-check for a null PDF.
type ReviewResult = SanitizeResult & { pdf_base64: string }

type Step =
  | { step: 'pick' }
  | { step: 'password'; error: string | null }
  | { step: 'working' }
  | { step: 'review'; result: ReviewResult }
  | { step: 'no-text' }
  | { step: 'failed'; message: string }

// What the last run was given, and what the user has clicked toward since.
// Every edit on the review screen writes to the draft and nothing re-runs
// until the one button is pressed: the work is not cancellable, so two runs
// in flight can finish out of order and paint a preview that is missing the
// redaction the screen already shows as applied.
interface Options {
  redact: string[]
  redactAmounts: boolean
}

const NO_OPTIONS: Options = { redact: [], redactAmounts: false }

function sameOptions(a: Options, b: Options): boolean {
  if (a.redactAmounts !== b.redactAmounts) return false
  if (a.redact.length !== b.redact.length) return false
  return a.redact.every((w) => b.redact.includes(w))
}

function pdfBlobFromBase64(base64: string): Blob {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type: 'application/pdf' })
}

function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const PARSE_HEADLINE: Record<SanitizeParseStatus, string> = {
  parsed: 'The app can already read this statement',
  unsupported: 'The app cannot read this statement yet',
  error: 'The app knows this bank but could not finish reading the statement',
}

const PARSE_BODY: Record<SanitizeParseStatus, string> = {
  parsed:
    'That is not a problem. A sample of a format that already works is still worth having, because it is what proves a future change did not quietly break it.',
  unsupported: 'This is exactly the case the sample is for. Nothing is wrong with your file.',
  error: 'This is worth sending. It points at a real gap in a parser that already half works.',
}

// Only what the user typed and facts with a fixed, closed set of values.
// This URL is the one thing on this page that leaves the machine, and the
// omnibox, browser history and any corporate proxy see it before the user
// has even read the form it opens. Nothing derived from the file's contents
// or its name belongs in it.
function githubIssueUrl(bank: string, result: SanitizeResult): string {
  const notes = [
    'Sanitized with the in-app "Help add your bank" page.',
    `Pages: ${result.page_count}`,
    PARSE_HEADLINE[result.parse_status] + '.',
  ].join('\n')
  const params = new URLSearchParams({
    template: 'bank-support.yml',
    bank: bank.trim(),
    notes,
  })
  return `${GITHUB_NEW_ISSUE}?${params.toString()}`
}

const NOTE_TONES = {
  info: { bg: 'var(--color-input)', border: 'var(--color-border)', fg: 'var(--color-text-2)' },
  success: {
    bg: 'var(--color-success-surface)',
    border: 'var(--color-success-surface-border)',
    fg: 'var(--color-success-text)',
  },
  danger: {
    bg: 'var(--color-danger-surface)',
    border: 'var(--color-danger-surface-border)',
    fg: 'var(--color-danger-text)',
  },
} as const

function Note({
  tone = 'info',
  icon: Icon,
  title,
  children,
}: {
  tone?: keyof typeof NOTE_TONES
  icon: LucideIcon
  title: string
  children: ReactNode
}) {
  const { bg, border, fg } = NOTE_TONES[tone]
  return (
    <div className="rounded-2lg px-3.5 py-3 flex items-start gap-2.5" style={{ background: bg, border: `1px solid ${border}` }}>
      <Icon size={13} className="shrink-0 mt-0.5" style={{ color: fg }} />
      <div className="flex flex-col gap-1 min-w-0">
        <div className="text-md font-semibold" style={{ color: fg }}>
          {title}
        </div>
        <div className="text-md text-muted leading-relaxed">{children}</div>
      </div>
    </div>
  )
}

function StepCard({
  n,
  title,
  subtitle,
  children,
}: {
  n: number
  title: string
  subtitle?: ReactNode
  children: ReactNode
}) {
  return (
    <Card className="flex flex-col gap-4">
      <div className="flex items-center gap-2.5">
        <div className="w-6 h-6 rounded-md bg-accent/12 text-accent text-2xs font-bold flex items-center justify-center shrink-0">
          {n}
        </div>
        <div className="min-w-0">
          <div className="text-base font-bold font-display">{title}</div>
          {subtitle && <div className="text-md text-muted mt-0.5 leading-relaxed">{subtitle}</div>}
        </div>
      </div>
      {children}
    </Card>
  )
}

// A toggle chip, not a labelled button - Button's variants are all "confirm
// or cancel a form", and a list of forty of them would read as forty
// actions. Both class strings are written out in full so Tailwind's scanner
// actually sees them.
function WordChip({ word, marked, onToggle }: { word: string; marked: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={marked}
      className={
        marked
          ? 'px-2 py-1 rounded-md text-xs font-mono cursor-pointer border border-accent bg-accent/15 text-text line-through'
          : 'px-2 py-1 rounded-md text-xs font-mono cursor-pointer border border-border bg-input text-text-2 hover:border-accent/50'
      }
    >
      {word}
    </button>
  )
}

function PasswordPrompt({
  errorMessage,
  onCancel,
  onSubmit,
}: {
  errorMessage: string | null
  onCancel: () => void
  onSubmit: (password: string) => void
}) {
  const [password, setPassword] = useState('')
  return (
    <Modal onClose={onCancel} title="Password Protected">
      <div className="text-md text-muted mb-4 leading-relaxed">
        This statement is locked. Enter the password your bank uses for it, usually your NRIC or date of birth.
        It is used here on your own machine to open the file, and is never saved or sent anywhere.
      </div>
      <Input
        autoFocus
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && password && onSubmit(password)}
        placeholder="PDF password"
        className="mb-2"
      />
      {errorMessage && <div className="text-xs text-danger-text mb-2">{errorMessage}</div>}
      <div className="flex justify-end gap-2.5 mt-4">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant="primary" onClick={() => password && onSubmit(password)}>
          Unlock
        </Button>
      </div>
    </Modal>
  )
}

interface PickedFile {
  name: string
  size: number
  bytes: Blob
}

export function Contribute() {
  const settingsQ = useSettings()
  const sanitize = useSanitizeStatement()
  const { setGlobalDropSuspended } = useUploadDialog()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [state, setState] = useState<Step>({ step: 'pick' })
  const [bank, setBank] = useState('')
  const [file, setFile] = useState<PickedFile | null>(null)
  const [pickError, setPickError] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [applied, setApplied] = useState<Options>(NO_OPTIONS)
  const [draft, setDraft] = useState<Options>(NO_OPTIONS)
  // The server derives the download's filename from the typed bank, so a
  // bank edited after a run leaves a result whose filename disagrees with
  // what the GitHub link says. Tracked here so that edit counts as a change
  // the re-check has to pick up, like any other.
  const [appliedBank, setAppliedBank] = useState('')
  // Which result's warning has been read, rather than a boolean that a
  // re-run would have to remember to reset. A re-check can surface a
  // different problem, and an acknowledgement carried over from the previous
  // file would hand out the GitHub button for a warning nobody saw.
  const [warningReadFor, setWarningReadFor] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  // The app-wide drop handler would otherwise claim a file dropped here and
  // start a real import into the user's own history.
  useEffect(() => {
    setGlobalDropSuspended(true)
    return () => setGlobalDropSuspended(false)
  }, [setGlobalDropSuspended])

  const pdfBase64 = state.step === 'review' ? state.result.pdf_base64 : null

  // The cleanup runs both before the next run's URL is made and on unmount.
  // Without it the previous blob - the LESS redacted PDF - stays reachable
  // for as long as the tab is open.
  useEffect(() => {
    if (!pdfBase64) {
      setPreviewUrl(null)
      return
    }
    const url = URL.createObjectURL(pdfBlobFromBase64(pdfBase64))
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [pdfBase64])

  async function acceptFile(picked: File) {
    if (!isPdf(picked)) {
      setPickError(`"${picked.name}" is not a PDF. Bank statements download as PDFs.`)
      return
    }
    try {
      const buffer = await picked.arrayBuffer()
      setPickError(null)
      setFile({ name: picked.name, size: picked.size, bytes: new Blob([buffer], { type: 'application/pdf' }) })
    } catch {
      // A File from an <input> is a live handle to the file on disk. Reading
      // the bytes up front means a session of chip-clicking cannot fail
      // minutes later because the file moved.
      setPickError('Could not read that file. If it has moved or been renamed, pick it again.')
    }
  }

  async function run(options: Options, withPassword: string) {
    if (!file) return
    setState({ step: 'working' })
    try {
      const result = await sanitize.mutateAsync({
        bytes: file.bytes,
        bank: bank.trim(),
        password: withPassword,
        redact: options.redact,
        redactAmounts: options.redactAmounts,
      })
      setApplied(options)
      setDraft(options)
      setAppliedBank(bank.trim())
      setPassword(withPassword)
      if (result.refusal_reason === 'no_text') {
        setState({ step: 'no-text' })
        return
      }
      if (!result.pdf_base64) {
        setState({ step: 'failed', message: 'The app finished but produced no file. That is a bug worth reporting.' })
        return
      }
      setState({ step: 'review', result: { ...result, pdf_base64: result.pdf_base64 } })
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === 'ENCRYPTED_PDF_PASSWORD_REQUIRED') {
          setState({ step: 'password', error: null })
          return
        }
        if (e.code === 'INCORRECT_PDF_PASSWORD') {
          setState({ step: 'password', error: e.message })
          return
        }
        setState({ step: 'failed', message: e.message })
        return
      }
      setState({ step: 'failed', message: 'Something went wrong while checking this file.' })
    }
  }

  function startOver() {
    setState({ step: 'pick' })
    setFile(null)
    setPickError(null)
    setPassword('')
    setApplied(NO_OPTIONS)
    setDraft(NO_OPTIONS)
  }

  function toggleWord(word: string) {
    setDraft((prev) =>
      prev.redact.includes(word)
        ? { ...prev, redact: prev.redact.filter((w) => w !== word) }
        : { ...prev, redact: [...prev.redact, word] },
    )
  }

  function download(result: ReviewResult) {
    if (!previewUrl) return
    const link = document.createElement('a')
    link.href = previewUrl
    link.download = result.suggested_filename
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  const supportedBanks = settingsQ.data?.supported_banks ?? []
  const canSubmit = !!file && bank.trim().length > 0

  return (
    <PageShell
      title="Help add your bank"
      subtitle="Turn one of your own statements into a sample someone can write a parser against, with your details taken out first."
      icon={HeartHandshake}
      maxWidth="max-w-3xl"
    >
      <div className="flex flex-col gap-4">
        <Note icon={ShieldCheck} title="Nothing has been sent anywhere">
          All of this happens inside the app, on this computer. The file stays here until you attach it to GitHub
          yourself, and you get to look at exactly what you would be attaching before you do.
        </Note>

        {settingsQ.isError ? (
          <Card>
            <ErrorState
              title="Cannot reach the app's backend"
              description="This page needs the app running to strip your statement. Check that it is still running and try again."
              onRetry={() => settingsQ.refetch()}
            />
          </Card>
        ) : (
          <>
            <StepCard
              n={1}
              title="Pick a statement"
              subtitle="One PDF, straight from your bank. The app opens it here, replaces everything that could identify you, and shows you the result."
            >
              <Field
                label="Which bank is this from?"
                hint={
                  supportedBanks.length
                    ? `Already working: ${supportedBanks.join(', ')}. Any other bank is the one worth sending.`
                    : undefined
                }
              >
                <Input
                  value={bank}
                  onChange={(e) => setBank(e.target.value)}
                  placeholder="For example: Standard Chartered"
                />
              </Field>

              {file ? (
                <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-input px-3.5 py-3">
                  <div className="min-w-0">
                    <div className="text-md text-text truncate" title={file.name}>
                      {file.name}
                    </div>
                    <div className="text-2xs text-muted-2">{formatSize(file.size)}</div>
                  </div>
                  <Button size="sm" variant="ghost" onClick={startOver}>
                    Choose another
                  </Button>
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setDragOver(true)
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setDragOver(false)
                  }}
                  onDrop={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    setDragOver(false)
                    const dropped = e.dataTransfer.files?.[0]
                    if (dropped) acceptFile(dropped)
                  }}
                  className={
                    dragOver
                      ? 'border-2 border-dashed border-accent rounded-xl px-6 py-9 text-center cursor-pointer bg-accent/10 transition-colors'
                      : 'border-2 border-dashed border-border rounded-xl px-6 py-9 text-center cursor-pointer bg-input/40 hover:border-accent transition-colors'
                  }
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={(e) => {
                      const picked = e.target.files?.[0]
                      if (picked) acceptFile(picked)
                      e.target.value = ''
                    }}
                  />
                  <div className="w-11 h-11 rounded-xl bg-accent/12 mx-auto mb-3.5 flex items-center justify-center">
                    <FileUp size={18} className="text-accent" />
                  </div>
                  <div className="text-sm font-semibold text-text mb-1.5">Drop your statement PDF here</div>
                  <div className="text-xs text-muted mb-4">Or click to browse. One file at a time.</div>
                  <Button variant="primary">Browse Files</Button>
                </div>
              )}

              {pickError && <div className="text-xs text-danger-text">{pickError}</div>}

              {/* Only on the first step. Once there is a result, the one
                  button that re-runs is the re-check further down, so there
                  is never a second control racing it. */}
              {state.step === 'pick' && (
                <div className="flex items-center gap-3">
                  <Button variant="primary" disabled={!canSubmit} onClick={() => run(draft, password)}>
                    Strip my details out
                  </Button>
                  {!canSubmit && (
                    <span className="text-2xs text-muted-2">
                      {file ? 'Type the bank name first.' : 'Pick a file first.'}
                    </span>
                  )}
                </div>
              )}
            </StepCard>

            {state.step === 'working' && (
              <StepCard n={2} title="Working on it">
                <div className="text-md text-muted leading-relaxed">
                  Reading every word, replacing anything the app does not recognize as your bank's own wording, and
                  drawing a brand new PDF from what is left. A long statement takes a few seconds.
                </div>
              </StepCard>
            )}

            {state.step === 'no-text' && (
              <StepCard n={2} title="There is no text in this PDF">
                <Note tone="danger" icon={AlertTriangle} title="This one cannot be used">
                  This file is a scan or a photo of a statement, so there are no words in it to work with, and
                  nothing a parser could ever read. Log in to your bank's website and download the original PDF
                  statement instead of printing it, scanning it or screenshotting it.
                </Note>
                <div>
                  <Button onClick={startOver}>Try a different file</Button>
                </div>
              </StepCard>
            )}

            {state.step === 'failed' && (
              <Card className="flex flex-col">
                <ErrorState title="Could not check this file" description={state.message} onRetry={() => run(draft, password)} />
                <div className="flex justify-center">
                  <Button variant="ghost" size="sm" onClick={startOver}>
                    Pick a different file
                  </Button>
                </div>
              </Card>
            )}

            {state.step === 'review' && (
              <>
                <ReviewSection
                  result={state.result}
                  draft={draft}
                  applied={applied}
                  dirty={!sameOptions(draft, applied) || bank.trim() !== appliedBank}
                  previewUrl={previewUrl}
                  onToggleWord={toggleWord}
                  onToggleAmounts={(v) => setDraft((prev) => ({ ...prev, redactAmounts: v }))}
                  onRecheck={() => run(draft, password)}
                />
                <ShareSection
                  bank={bank}
                  result={state.result}
                  acknowledged={warningReadFor === state.result.pdf_base64}
                  onAcknowledge={() => setWarningReadFor(state.result.pdf_base64)}
                  onDownload={() => download(state.result)}
                  previewReady={!!previewUrl}
                />
              </>
            )}
          </>
        )}
      </div>

      {state.step === 'password' && (
        <PasswordPrompt
          errorMessage={state.error}
          onCancel={() => setState({ step: 'pick' })}
          onSubmit={(pw) => run(draft, pw)}
        />
      )}
    </PageShell>
  )
}

function ReviewSection({
  result,
  draft,
  applied,
  dirty,
  previewUrl,
  onToggleWord,
  onToggleAmounts,
  onRecheck,
}: {
  result: ReviewResult
  draft: Options
  applied: Options
  dirty: boolean
  previewUrl: string | null
  onToggleWord: (word: string) => void
  onToggleAmounts: (value: boolean) => void
  onRecheck: () => void
}) {
  const alreadyRemoved = applied.redact.filter((w) => !result.kept_words.includes(w))

  return (
    <StepCard
      n={2}
      title="Check what is left"
      subtitle={`${result.word_count.toLocaleString()} words across ${result.page_count} page${result.page_count === 1 ? '' : 's'}.`}
    >
      {result.problems.length > 0 && (
        <Note tone="danger" icon={AlertTriangle} title="The app's own check was not happy with this one">
          <ul className="flex flex-col gap-1.5 mb-2">
            {result.problems.map((problem) => (
              <li key={problem} className="flex items-start gap-2">
                <span className="w-1 h-1 rounded-full bg-danger-text shrink-0 mt-2" />
                <span className="min-w-0">{problem}</span>
              </li>
            ))}
          </ul>
          You can still download it, and you may decide it is fine. Read the preview below properly first.
        </Note>
      )}

      <div>
        <div className="text-md font-semibold text-text">Words kept exactly as they were</div>
        <div className="text-md text-muted leading-relaxed mt-1">
          Everything else on the statement has been replaced. These words survived because the app recognized them
          as your bank's own wording. Click anything here that is actually about you, then press the button below.
        </div>
        <div className="text-xs text-muted-2 leading-relaxed mt-1.5">
          Amounts, dates and short numbers are kept as well, and are not in this list. So this list is not the whole
          story. The preview further down is, and it is the only complete view of what you would be sharing.
        </div>
        <div className="flex flex-wrap gap-1.5 mt-3">
          {result.kept_words.length === 0 ? (
            <span className="text-md text-muted">No words survived at all.</span>
          ) : (
            result.kept_words.map((word) => (
              <WordChip key={word} word={word} marked={draft.redact.includes(word)} onToggle={() => onToggleWord(word)} />
            ))
          )}
        </div>
      </div>

      {result.oddities.length > 0 && (
        <div>
          <div className="text-md font-semibold text-text">Odd bits that are neither words nor money</div>
          <div className="text-md text-muted leading-relaxed mt-1">
            Reference codes and the like. This short list is where something that identifies you is most likely to
            be hiding, so it is worth reading every one.
          </div>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {result.oddities.map((word) => (
              <WordChip key={word} word={word} marked={draft.redact.includes(word)} onToggle={() => onToggleWord(word)} />
            ))}
          </div>
        </div>
      )}

      {alreadyRemoved.length > 0 && (
        <div>
          <div className="text-md font-semibold text-text">Already taken out</div>
          <div className="text-md text-muted leading-relaxed mt-1">Click one to put it back.</div>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {alreadyRemoved.map((word) => (
              <WordChip key={word} word={word} marked={draft.redact.includes(word)} onToggle={() => onToggleWord(word)} />
            ))}
          </div>
        </div>
      )}

      <details className="rounded-lg border border-border bg-input/40 px-3.5 py-2.5">
        <summary className="text-md text-muted cursor-pointer select-none">Advanced</summary>
        <label className="flex items-start gap-2.5 mt-3 cursor-pointer">
          <span className="mt-0.5">
            <Checkbox checked={draft.redactAmounts} onChange={onToggleAmounts} />
          </span>
          <span className="min-w-0">
            <span className="text-md text-text">Replace the amounts too</span>
            <span className="block text-xs text-muted leading-relaxed mt-1">
              Every figure becomes a made-up number of the same shape. This also breaks the totals a parser is
              tested against, so the sample can no longer prove that a parser reads it correctly. Leave it off
              unless the amounts themselves are what worries you.
            </span>
          </span>
        </label>
      </details>

      <div>
        <div className="text-md font-semibold text-text">The file you would be sharing</div>
        <div className="text-xs text-muted-2 mt-1 mb-2.5">Every page of it. Scroll through the whole thing.</div>
        {previewUrl ? (
          <iframe
            src={previewUrl}
            title="The sanitized statement, exactly as it would be shared"
            className="w-full h-[520px] rounded-lg border border-border bg-input"
          />
        ) : (
          <div className="text-md text-muted">Building the preview.</div>
        )}
      </div>

      <Note icon={Info} title={PARSE_HEADLINE[result.parse_status]}>
        {PARSE_BODY[result.parse_status]}
        {result.detected_bank && (
          <div className="mt-1.5">
            Recognized as <span className="text-text">{result.detected_bank}</span>.
          </div>
        )}
        {result.account_summaries.length > 0 && (
          <div className="mt-1.5">
            Read {result.account_summaries.length === 1 ? 'one account' : `${result.account_summaries.length} accounts`}:{' '}
            {result.account_summaries
              .map((a) => `${a.account_type} (${a.transaction_count} transactions)`)
              .join(', ')}
            .
          </div>
        )}
        {/* Deliberately no copy button. This can quote real figures off the
            statement, and the obvious next click for anyone who had one
            would be to paste it into a public issue. */}
        {result.parse_detail && (
          <div className="mt-2 font-mono text-xs text-muted-2 leading-relaxed break-words">{result.parse_detail}</div>
        )}
      </Note>

      <div className="flex items-center gap-3">
        <Button variant="primary" disabled={!dirty} onClick={onRecheck}>
          Remove these and re-check
        </Button>
        <span className="text-2xs text-muted-2">
          {dirty
            ? 'One re-check applies everything you have changed, all at once.'
            : 'Nothing selected to change.'}
        </span>
      </div>
    </StepCard>
  )
}

function ShareSection({
  bank,
  result,
  acknowledged,
  onAcknowledge,
  onDownload,
  previewReady,
}: {
  bank: string
  result: ReviewResult
  acknowledged: boolean
  onAcknowledge: () => void
  onDownload: () => void
  previewReady: boolean
}) {
  const hasProblems = result.problems.length > 0
  const githubHidden = hasProblems && !acknowledged

  return (
    <StepCard n={3} title="Send it in" subtitle="Two clicks and one drag. Nothing is automatic, you attach the file yourself.">
      <div>
        <Button variant={hasProblems ? 'danger-outline' : 'primary'} disabled={!previewReady} onClick={onDownload}>
          {hasProblems ? 'Download anyway' : 'Download the sanitized file'}
        </Button>
        <div className="text-2xs text-muted-2 mt-1.5 font-mono">{result.suggested_filename}</div>
      </div>

      <ol className="flex flex-col gap-2">
        {[
          "Click Download above. Save it somewhere you'll find it.",
          'Click "Open the GitHub form" - it opens in your browser, already filled in with your bank and what we found.',
          'Drag the downloaded file into the box on that page.',
          'Click "Create". Done.',
        ].map((line, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <span className="w-5 h-5 rounded-md bg-input text-accent text-2xs font-bold flex items-center justify-center shrink-0 mt-0.5">
              {i + 1}
            </span>
            <span className="text-md text-muted leading-relaxed pt-0.5">{line}</span>
          </li>
        ))}
      </ol>

      {githubHidden ? (
        <div className="flex items-center gap-3">
          <Button onClick={onAcknowledge}>I have read the warning above</Button>
          <span className="text-2xs text-muted-2">The GitHub form opens once you have.</span>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            onClick={() => window.open(githubIssueUrl(bank, result), '_blank', 'noopener,noreferrer')}
          >
            <span className="flex items-center gap-2">
              <ExternalLink size={14} />
              Open the GitHub form
            </span>
          </Button>
          <span className="text-2xs text-muted-2">Opens a new tab. You will need a GitHub account.</span>
        </div>
      )}

      <Note icon={Lock} title="Only the bank name travels in that link">
        The address the button opens carries what you typed as the bank, the page count, and whether the app could
        read the statement. None of the words above, none of the figures, and not the name of the file you picked.
      </Note>
    </StepCard>
  )
}
