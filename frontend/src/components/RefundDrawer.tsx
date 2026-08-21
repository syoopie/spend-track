import { useRefundPairing } from '../api/hooks'
import type { Transaction } from '../api/types'
import { fmtDate, fmtSigned } from '../lib/format'

function TxCard({ tx }: { tx: Transaction }) {
  return (
    <div className="border border-border rounded-[10px] p-3.5">
      <div className="text-[13px] font-semibold">{tx.raw_description}</div>
      <div className="text-xs text-muted my-1">
        {fmtDate(tx.transaction_date)} · {tx.category} · {tx.bank_name} {tx.account_number_masked}
      </div>
      <div className={`font-mono text-[15px] ${tx.amount > 0 ? 'text-success' : 'text-text'}`}>
        {fmtSigned(tx.amount)}
      </div>
    </div>
  )
}

export function RefundDrawer({ transactionId, onClose }: { transactionId: number; onClose: () => void }) {
  const { data, isLoading } = useRefundPairing(transactionId)

  return (
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/55 z-40" />
      <div className="fixed top-0 right-0 h-full w-[380px] bg-card shadow-2xl z-50 p-6 overflow-y-auto border-l border-border">
        <div className="flex justify-between items-center mb-4.5">
          <div className="text-[15px] font-bold">Refund Pairing</div>
          <button onClick={onClose} className="border-none bg-transparent text-lg cursor-pointer text-muted-2">
            ×
          </button>
        </div>
        {isLoading && <div className="text-muted text-sm">Loading…</div>}
        {data && (
          <>
            <div className="text-xs text-muted-2 mb-2">ORIGINAL TRANSACTION</div>
            <div className="mb-3">
              <TxCard tx={data.original} />
            </div>
            <div className="text-center text-dim text-base mb-3">↓ netted against ↓</div>
            <TxCard tx={data.refund} />
          </>
        )}
      </div>
    </>
  )
}
