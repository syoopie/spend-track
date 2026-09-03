import type { ApiErrorBody } from './types'

export class ApiError extends Error {
  code: string
  status: number
  constructor(status: number, body: ApiErrorBody) {
    super(body.message)
    this.code = body.code
    this.status = status
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: ApiErrorBody = { code: 'UNKNOWN_ERROR', message: res.statusText }
    try {
      const json = await res.json()
      if (json?.detail?.code) body = json.detail
    } catch {
      // ignore parse failure, fall back to statusText
    }
    throw new ApiError(res.status, body)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

function qs(params?: Record<string, string | number | boolean | undefined | null>): string {
  if (!params) return ''
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
  if (!entries.length) return ''
  return '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
}

export const api = {
  get<T>(path: string, params?: Record<string, string | number | boolean | undefined | null>): Promise<T> {
    return fetch(`/api${path}${qs(params)}`).then((r) => handle<T>(r))
  },
  post<T>(path: string, body?: unknown): Promise<T> {
    return fetch(`/api${path}`, {
      method: 'POST',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).then((r) => handle<T>(r))
  },
  patch<T>(path: string, body: unknown): Promise<T> {
    return fetch(`/api${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((r) => handle<T>(r))
  },
  delete<T>(path: string, params?: Record<string, string | number | boolean | undefined | null>): Promise<T> {
    return fetch(`/api${path}${qs(params)}`, { method: 'DELETE' }).then((r) => handle<T>(r))
  },
  upload<T>(path: string, file: File, extra?: Record<string, string>): Promise<T> {
    const form = new FormData()
    form.append('file', file)
    for (const [k, v] of Object.entries(extra ?? {})) form.append(k, v)
    return fetch(`/api${path}`, { method: 'POST', body: form }).then((r) => handle<T>(r))
  },
  // `upload`'s Record<string, string> can't express a field that repeats
  // (multipart allows it, an object key doesn't), and the sanitize endpoint
  // takes one `redact` field per word. Ordered pairs instead of bending the
  // existing signature. The filename is passed explicitly so a caller can
  // send bytes under a name of its own choosing rather than the one the
  // user picked off their disk.
  uploadFields<T>(path: string, file: Blob, filename: string, fields: [string, string][]): Promise<T> {
    const form = new FormData()
    form.append('file', file, filename)
    for (const [k, v] of fields) form.append(k, v)
    return fetch(`/api${path}`, { method: 'POST', body: form }).then((r) => handle<T>(r))
  },
  uploadMultiple<T>(path: string, files: File[], extra?: Record<string, string>): Promise<T> {
    const form = new FormData()
    for (const file of files) form.append('files', file)
    for (const [k, v] of Object.entries(extra ?? {})) form.append(k, v)
    return fetch(`/api${path}`, { method: 'POST', body: form }).then((r) => handle<T>(r))
  },
}
