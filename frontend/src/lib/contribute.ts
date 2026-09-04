// Pure helpers behind the Contribute page ("Help add your bank"). Kept out of
// the component so the file that renders the flow is just the flow.

import type { SanitizeParseStatus, SanitizeResult } from '../api/types'

const GITHUB_NEW_ISSUE = 'https://github.com/syoopie/spend-track/issues/new'

// A result on the review step always carries a file. The two reasons it might
// not - a scan with no text, and an outright failure - are their own steps, so
// nothing downstream of the review step has to re-check for a null PDF.
export type ReviewResult = SanitizeResult & { pdf_base64: string }

// The whole page is one of these at a time. `review` carries the snapshot of
// the run that produced it - what options it was given, the bank name at that
// point, whether its warning has been read - so that "has the user changed
// anything since?" is one comparison and an acknowledgement can never carry
// over to a different result.
export type Step =
  | { step: 'pick' }
  | { step: 'password'; error: string | null }
  | { step: 'working' }
  | { step: 'review'; result: ReviewResult; applied: Options; appliedBank: string; warningRead: boolean }
  | { step: 'no-text' }
  | { step: 'failed'; message: string }

export interface Options {
  redact: string[]
  redactAmounts: boolean
}

export const NO_OPTIONS: Options = { redact: [], redactAmounts: false }

export function sameOptions(a: Options, b: Options): boolean {
  if (a.redactAmounts !== b.redactAmounts) return false
  if (a.redact.length !== b.redact.length) return false
  return a.redact.every((w) => b.redact.includes(w))
}

export function pdfBlobFromBase64(base64: string): Blob {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return new Blob([bytes], { type: 'application/pdf' })
}

export function isPdf(file: File): boolean {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export const PARSE_HEADLINE: Record<SanitizeParseStatus, string> = {
  parsed: 'The app can already read this statement',
  unsupported: 'The app cannot read this statement yet',
  error: 'The app knows this bank but could not finish reading the statement',
}

export const PARSE_BODY: Record<SanitizeParseStatus, string> = {
  parsed:
    'That is not a problem. A sample of a format that already works is still worth having, because it is what proves a future change did not quietly break it.',
  unsupported: 'This is exactly the case the sample is for. Nothing is wrong with your file.',
  error: 'This is worth sending. It points at a real gap in a parser that already half works.',
}

// Only what the user typed and facts with a fixed, closed set of values. This
// URL is the one thing on this page that leaves the machine, and the omnibox,
// browser history and any corporate proxy see it before the user has even read
// the form it opens. Nothing derived from the file's contents or its name
// belongs in it.
export function githubIssueUrl(bank: string, result: SanitizeResult): string {
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
