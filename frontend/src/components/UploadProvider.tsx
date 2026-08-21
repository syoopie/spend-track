import { FileUp } from 'lucide-react'
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useCurrentStagingBatch, useUploadStatement } from '../api/hooks'
import { ApiError } from '../api/client'
import { Modal } from './Modal'
import { StagingReviewDialog } from './StagingReviewDialog'

interface UploadContextValue {
  openDialog: () => void
  openReview: () => void
  hasPendingBatch: boolean
}

const UploadContext = createContext<UploadContextValue | null>(null)

export function useUploadDialog() {
  const ctx = useContext(UploadContext)
  if (!ctx) throw new Error('useUploadDialog must be used within UploadProvider')
  return ctx
}

function isPdfFile(file: File) {
  return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
}

function hasFiles(e: DragEvent) {
  return !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files')
}

function PasswordModal({
  filename,
  errorMessage,
  onCancel,
  onSubmit,
}: {
  filename: string
  errorMessage: string | null
  onCancel: () => void
  onSubmit: (password: string) => void
}) {
  const [password, setPassword] = useState('')
  return (
    <Modal onClose={onCancel}>
      <div className="text-base font-bold mb-2.5">Password Protected</div>
      <div className="text-[13px] text-muted mb-4 leading-relaxed">
        <span className="text-text font-medium">{filename}</span> is encrypted. Enter its password to unlock it -
        processing happens locally and the password is never saved. The same password is tried against every file
        in this upload.
      </div>
      <input
        autoFocus
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && password && onSubmit(password)}
        placeholder="PDF password"
        className="w-full box-border px-3 py-2.5 rounded-lg border border-border bg-input text-text text-[13px] mb-2"
      />
      {errorMessage && <div className="text-[12px] text-danger-text mb-2">{errorMessage}</div>}
      <div className="flex justify-end gap-2.5 mt-4">
        <button
          onClick={onCancel}
          className="text-[13px] px-4 py-2.5 rounded-lg border border-border bg-input text-text cursor-pointer"
        >
          Cancel
        </button>
        <button
          onClick={() => password && onSubmit(password)}
          className="text-[13px] font-semibold px-4 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer"
        >
          Unlock
        </button>
      </div>
    </Modal>
  )
}

export function UploadProvider({ children }: { children: ReactNode }) {
  const upload = useUploadStatement()
  const pendingBatchQ = useCurrentStagingBatch()
  const hasPendingBatch = !!pendingBatchQ.data
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [reviewOpen, setReviewOpen] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const dragCounter = useRef(0)

  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function handleFiles(files: File[], password?: string) {
    if (hasPendingBatch || files.length === 0) return
    if (!password) {
      const nonPdf = files.find((f) => !isPdfFile(f))
      if (nonPdf) {
        setErrorMessage(`"${nonPdf.name}" is not a PDF - only PDF statements are supported.`)
        setDialogOpen(true)
        return
      }
    }
    setErrorMessage(null)
    setPasswordError(null)
    try {
      await upload.mutateAsync({ files, password })
      setDialogOpen(false)
      setPasswordModalOpen(false)
      setPendingFiles([])
      setReviewOpen(true)
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === 'ENCRYPTED_PDF_PASSWORD_REQUIRED') {
          setPendingFiles(files)
          setPasswordModalOpen(true)
          return
        }
        if (e.code === 'INCORRECT_PDF_PASSWORD') {
          setPendingFiles(files)
          setPasswordModalOpen(true)
          setPasswordError(e.message)
          return
        }
        setErrorMessage(e.message)
        setDialogOpen(true)
      } else {
        setErrorMessage('Something went wrong uploading these files.')
        setDialogOpen(true)
      }
    }
  }

  // Kept fresh via ref so the window listeners (registered once) always call
  // the latest closure without needing to re-attach on every render.
  const handleFilesRef = useRef(handleFiles)
  handleFilesRef.current = handleFiles
  const hasPendingBatchRef = useRef(hasPendingBatch)
  hasPendingBatchRef.current = hasPendingBatch

  useEffect(() => {
    function onDragEnter(e: DragEvent) {
      if (!hasFiles(e) || hasPendingBatchRef.current) return
      e.preventDefault()
      dragCounter.current++
      setDragActive(true)
    }
    function onDragOver(e: DragEvent) {
      if (!hasFiles(e) || hasPendingBatchRef.current) return
      e.preventDefault()
    }
    function onDragLeave(e: DragEvent) {
      if (!hasFiles(e)) return
      e.preventDefault()
      dragCounter.current = Math.max(0, dragCounter.current - 1)
      if (dragCounter.current === 0) setDragActive(false)
    }
    function onDrop(e: DragEvent) {
      if (!hasFiles(e) || hasPendingBatchRef.current) return
      e.preventDefault()
      dragCounter.current = 0
      setDragActive(false)
      const files = Array.from(e.dataTransfer?.files ?? [])
      if (files.length) handleFilesRef.current(files)
    }
    window.addEventListener('dragenter', onDragEnter)
    window.addEventListener('dragover', onDragOver)
    window.addEventListener('dragleave', onDragLeave)
    window.addEventListener('drop', onDrop)
    return () => {
      window.removeEventListener('dragenter', onDragEnter)
      window.removeEventListener('dragover', onDragOver)
      window.removeEventListener('dragleave', onDragLeave)
      window.removeEventListener('drop', onDrop)
    }
  }, [])

  return (
    <UploadContext.Provider
      value={{
        openDialog: () => {
          if (hasPendingBatch) return
          setErrorMessage(null)
          setDialogOpen(true)
        },
        openReview: () => setReviewOpen(true),
        hasPendingBatch,
      }}
    >
      {children}

      {reviewOpen && <StagingReviewDialog onClose={() => setReviewOpen(false)} />}

      {dragActive && (
        <div className="fixed inset-0 z-[70] pointer-events-none flex items-center justify-center bg-accent/10 backdrop-blur-[2px]">
          <div className="border-2 border-dashed border-accent rounded-2xl px-16 py-12 bg-card/90 text-center">
            <div className="text-lg font-semibold text-text mb-1.5">Drop to upload statement(s)</div>
            <div className="text-[13px] text-muted">PDF e-statements · processed locally, never uploaded</div>
          </div>
        </div>
      )}

      {dialogOpen && (
        <Modal onClose={() => setDialogOpen(false)} width={460}>
          <div className="flex items-center justify-between mb-4">
            <div className="text-base font-bold">Upload Statement</div>
            <button
              onClick={() => setDialogOpen(false)}
              className="text-muted hover:text-text text-lg leading-none cursor-pointer border-none bg-transparent"
            >
              ×
            </button>
          </div>
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-border rounded-xl px-6 py-10 text-center cursor-pointer bg-input/40 hover:border-accent transition-colors"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf"
              multiple
              className="hidden"
              onChange={(e) => {
                const files = Array.from(e.target.files ?? [])
                if (files.length) handleFiles(files)
                e.target.value = ''
              }}
            />
            <div className="w-11 h-11 rounded-xl bg-accent/12 mx-auto mb-3.5 flex items-center justify-center">
              <FileUp size={18} className="text-accent" />
            </div>
            <div className="text-sm font-semibold text-text mb-1.5">
              Drag &amp; drop one or more PDFs anywhere in the app
            </div>
            <div className="text-[12px] text-muted mb-4">DBS, OCBC, or UOB e-statements · processed locally, never uploaded</div>
            <button
              disabled={upload.isPending}
              className="text-[13px] font-semibold px-4 py-2 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
            >
              {upload.isPending ? 'Uploading…' : 'Browse Files'}
            </button>
          </div>
          {errorMessage && <div className="text-center text-[12px] text-danger-text mt-3">{errorMessage}</div>}
        </Modal>
      )}

      {passwordModalOpen && pendingFiles.length > 0 && (
        <PasswordModal
          filename={pendingFiles.length === 1 ? pendingFiles[0].name : `${pendingFiles.length} files`}
          errorMessage={passwordError}
          onCancel={() => {
            setPasswordModalOpen(false)
            setPendingFiles([])
          }}
          onSubmit={(password) => handleFiles(pendingFiles, password)}
        />
      )}
    </UploadContext.Provider>
  )
}
