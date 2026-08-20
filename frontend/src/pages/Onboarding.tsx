import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useUploadStatement } from '../api/hooks'
import { ApiError } from '../api/client'
import { Modal } from '../components/Modal'

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
        processing happens locally and the password is never saved.
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

export function Onboarding() {
  const navigate = useNavigate()
  const upload = useUploadStatement()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [isDragging, setIsDragging] = useState(false)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  async function handleFile(file: File, password?: string) {
    setErrorMessage(null)
    setPasswordError(null)
    try {
      const batch = await upload.mutateAsync({ file, password })
      navigate(`/staging/${batch.batch_id}`)
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.code === 'ENCRYPTED_PDF_PASSWORD_REQUIRED') {
          setPendingFile(file)
          setPasswordModalOpen(true)
          return
        }
        if (e.code === 'INCORRECT_PDF_PASSWORD') {
          setPendingFile(file)
          setPasswordModalOpen(true)
          setPasswordError(e.message)
          return
        }
        setErrorMessage(e.message)
      } else {
        setErrorMessage('Something went wrong uploading this file.')
      }
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-10">
      <div className="w-full max-w-xl">
        <div className="flex items-center gap-2.5 mb-9 justify-center">
          <div className="w-7 h-7 rounded-lg bg-accent" />
          <div className="text-[15px] font-semibold text-text">Expenditure Tracker</div>
        </div>

        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setIsDragging(false)
            const file = e.dataTransfer.files[0]
            if (file) handleFile(file)
          }}
          className={`border-2 border-dashed rounded-2xl px-8 py-14 text-center cursor-pointer bg-card transition-colors ${
            isDragging ? 'border-accent' : 'border-border'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFile(file)
              e.target.value = ''
            }}
          />
          <div className="w-13 h-13 rounded-xl bg-accent/12 mx-auto mb-5 flex items-center justify-center">
            <svg width="22" height="22" viewBox="0 0 16 16">
              <path d="M8 11 V2" stroke="#e35fd0" strokeWidth="1.6" fill="none" />
              <polygon points="4.5,5.5 11.5,5.5 8,1.5" fill="#e35fd0" />
              <rect x="2" y="12.5" width="12" height="2" fill="none" stroke="#e35fd0" strokeWidth="1.6" />
            </svg>
          </div>
          <div className="text-xl font-semibold text-text mb-2.5">
            Drag &amp; Drop DBS, OCBC, or UOB
            <br />
            Statements to Start
          </div>
          <div className="text-[13px] text-muted mb-5.5">PDF e-statements · processed locally, never uploaded</div>
          <div className="flex gap-2 justify-center mb-5.5">
            {['DBS', 'OCBC', 'UOB'].map((b) => (
              <span
                key={b}
                className="text-[11px] font-semibold px-2.5 py-1.5 rounded-md bg-input text-muted border border-border"
              >
                {b}
              </span>
            ))}
          </div>
          <button
            disabled={upload.isPending}
            className="text-[13px] font-semibold px-5 py-2.5 rounded-lg border-none bg-accent text-accent-fg cursor-pointer disabled:opacity-60"
          >
            {upload.isPending ? 'Uploading…' : 'Browse Files →'}
          </button>
        </div>

        {errorMessage && (
          <div className="text-center text-[13px] text-danger-text mt-4">{errorMessage}</div>
        )}

        <div className="text-center text-xs text-muted-2 mt-4.5">
          Account details are detected automatically from statement headers — no manual setup.
        </div>
      </div>

      {passwordModalOpen && pendingFile && (
        <PasswordModal
          filename={pendingFile.name}
          errorMessage={passwordError}
          onCancel={() => {
            setPasswordModalOpen(false)
            setPendingFile(null)
          }}
          onSubmit={(password) => handleFile(pendingFile, password)}
        />
      )}
    </div>
  )
}
