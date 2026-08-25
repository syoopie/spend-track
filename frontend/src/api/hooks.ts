import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { api, ApiError } from './client'
import { useToast } from '../components/Toast'
import type {
  Account,
  AiSettings,
  AiSettingsUpdateRequest,
  AiStatus,
  BatchRow,
  BatchRowUpdateRequest,
  BatchRuleUndoRequest,
  CommitResult,
  Contact,
  ContactCreateRequest,
  ContactImportResult,
  ContactUpdateRequest,
  DashboardSummary,
  DeleteScopeResult,
  MatchCount,
  MonthlyTotal,
  PathCheckResult,
  RecategorizeBatch,
  RecategorizeCommitResult,
  RecategorizeRequest,
  RecategorizeRuleCreateResult,
  RefundPairing,
  Rule,
  RuleCreateRequest,
  RuleQuickCreateRequest,
  RuleRerunRowSnapshot,
  RuleUpdateRequest,
  Settings,
  SourceFileSummary,
  StagingBatch,
  StagingRuleCreateResult,
  Transaction,
  TransactionUpdateRequest,
  Category,
} from './types'

// Every mutation below that fires a user-visible toast falls back to this
// when the thrown error has no useful message of its own (e.g. a network
// failure) - see root cause 04 / X-3 in UI Review.dc.html: before this,
// most mutations were either fully silent or left a stale inline message
// only one screen bothered to render.
function errMsg(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

// --- accounts -----------------------------------------------------------

export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => api.get<Account[]>('/accounts') })
}

// --- transactions ---------------------------------------------------------

export function useTransactions(params: {
  date_from?: string
  date_to?: string
  account_id?: string
  include_excluded?: boolean
}) {
  return useQuery({
    queryKey: ['transactions', params],
    queryFn: () => api.get<Transaction[]>('/transactions', params),
    // Keeps last range's rows on screen while a new range/account fetches,
    // instead of the feed going blank/loading on every filter change -
    // DASH-1 in UI Review.dc.html.
    placeholderData: keepPreviousData,
  })
}

export function useUpdateTransaction() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: TransactionUpdateRequest }) =>
      api.patch<Transaction>(`/transactions/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      toast.success('Transaction updated.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't update the transaction.")),
  })
}

export function useDeleteTransaction() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    // No success toast - callers (Dashboard.tsx) show their own optimistic
    // "Transaction deleted - Undo" toast before this even fires, same
    // pattern as useDeleteRule.
    mutationFn: (id: number) => api.delete(`/transactions/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't delete the transaction.")),
  })
}

export function useSourceFiles() {
  return useQuery({ queryKey: ['source-files'], queryFn: () => api.get<SourceFileSummary[]>('/transactions/source-files') })
}

export function useDeleteTransactionsByFile() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (filename: string) => api.delete<DeleteScopeResult>('/transactions/by-file', { filename }),
    onSuccess: (data, filename) => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['source-files'] })
      toast.success(`Deleted ${data.deleted_count} transaction${data.deleted_count === 1 ? '' : 's'} from "${filename}".`)
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't delete those transactions.")),
  })
}

// --- recategorize -----------------------------------------------------------
//
// Deliberately "treated the exact same as an upload" (per the app's own
// UX): the POST proposes a pollable, reviewable, discardable batch - same
// shape and lifecycle as staging's StagingBatch/useCurrentStagingBatch,
// rendered in the same ReviewDialog with Commit/Discard - rather than
// writing straight to the DB. See engine/recategorize_job.py.

export function useRecategorizeTransactions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RecategorizeRequest) => api.post<RecategorizeBatch>('/transactions/recategorize', body),
    onSuccess: (data) => qc.setQueryData(['recategorize-batch', 'current'], data),
  })
}

export function useCurrentRecategorizeBatch(enabled: boolean) {
  return useQuery({
    queryKey: ['recategorize-batch', 'current'],
    queryFn: async () => {
      try {
        return await api.get<RecategorizeBatch>('/transactions/recategorize/current')
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
    enabled,
    refetchInterval: (query) => (query.state.data?.ai_status === 'running' ? 1500 : false),
  })
}

export function useRefundPairing(transactionId: number | null) {
  return useQuery({
    queryKey: ['refund-pairing', transactionId],
    queryFn: () => api.get<RefundPairing>(`/transactions/${transactionId}/refund-pairing`),
    enabled: transactionId != null,
  })
}

// --- dashboard --------------------------------------------------------------

export function useDashboardSummary(params: { date_from?: string; date_to?: string; account_id?: string }) {
  return useQuery({
    queryKey: ['dashboard-summary', params],
    queryFn: () => api.get<DashboardSummary>('/dashboard/summary', params),
    // See useTransactions above - this is the query whose key-change
    // triggered the original "whole page blanks on every filter change"
    // symptom (root cause 03 / DASH-1), since it gates Dashboard.tsx's
    // entire render.
    placeholderData: keepPreviousData,
  })
}

export function useMonthlyTotals(accountId?: string) {
  return useQuery({
    queryKey: ['monthly-totals', accountId],
    queryFn: () => api.get<MonthlyTotal[]>('/dashboard/monthly-totals', { account_id: accountId }),
    placeholderData: keepPreviousData,
  })
}

// --- statements / staging ------------------------------------------------------

export function useUploadStatement() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ files, password }: { files: File[]; password?: string }) =>
      api.uploadMultiple<StagingBatch>('/statements/upload', files, password ? { password } : undefined),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.setQueryData(['staging-batch', 'current'], data)
    },
  })
}

export function useCurrentStagingBatch() {
  return useQuery({
    queryKey: ['staging-batch', 'current'],
    queryFn: async () => {
      try {
        return await api.get<StagingBatch>('/statements/staging/current')
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return null
        throw e
      }
    },
    // Polls while the background AI pass is still working so the dialog's
    // banner/rows update live without the user having to do anything -
    // see StagingReviewDialog's ai_status banner.
    refetchInterval: (query) => (query.state.data?.ai_status === 'running' ? 1500 : false),
  })
}

// --- batch actions (staging + recategorize) ----------------------------------
//
// A staging batch and a recategorize batch share one backend row/action
// shape (see BatchRow/BatchRowUpdateRequest in types.ts) - what still
// differs between them is only how a batch is *seeded* (useUploadStatement vs
// useRecategorizeTransactions, above/below) and each kind's own URL prefix.
// Everything from "edit a row" through "commit/discard" is one parameterized
// set of hooks here, bundled by useBatchActions() into the single prop list
// StagingReviewDialog and RecategorizeReviewDialog both hand to the shared
// components/ReviewDialog.tsx.

export type BatchKind = 'staging' | 'recategorize'

function batchUrl(kind: BatchKind, batchId: string): string {
  return kind === 'staging' ? `/statements/staging/${batchId}` : `/transactions/recategorize/${batchId}`
}

function batchQueryKey(kind: BatchKind): string {
  return kind === 'staging' ? 'staging-batch' : 'recategorize-batch'
}

// Predicts engine/batch_review.py::apply_row_update's own field assignment
// for the plain (non restore_default) case, so the row list can update the
// instant a field is applied instead of waiting a full round trip (REV-2 in
// UI Review.dc.html). restore_default is deliberately NOT predicted here -
// its actual target depends on ai_category/original_category, which this
// generic hook has no visibility into - so that one action alone still
// waits for the real response; every other edit (category, label, the
// PayNow contact checkbox) is optimistic.
function optimisticRowPatch(row: BatchRow, body: BatchRowUpdateRequest): BatchRow {
  if (body.restore_default) return { ...row, needs_review: false }
  return {
    ...row,
    category: body.category,
    matched_label: body.matched_label ?? null,
    subcategory: body.subcategory ?? null,
    needs_review: false,
  }
}

function useUpdateBatchRow(kind: BatchKind, batchId: string) {
  const qc = useQueryClient()
  const queryKey = [batchQueryKey(kind), 'current']
  return useMutation({
    mutationFn: ({ key, body }: { key: number; body: BatchRowUpdateRequest }) =>
      api.patch<StagingBatch | RecategorizeBatch>(`${batchUrl(kind, batchId)}/rows/${key}`, body),
    onMutate: async ({ key, body }) => {
      await qc.cancelQueries({ queryKey })
      const previous = qc.getQueryData<StagingBatch | RecategorizeBatch>(queryKey)
      if (previous) {
        qc.setQueryData(queryKey, {
          ...previous,
          rows: previous.rows.map((r) => (r.key === key ? optimisticRowPatch(r, body) : r)),
        })
      }
      return { previous }
    },
    // Roll back to the exact pre-mutation snapshot on failure, not just an
    // invalidate/refetch - the row's field(s) should visibly snap back to
    // what they were, which is what tells the user the edit didn't stick.
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(queryKey, context.previous)
    },
    onSuccess: (data) => qc.setQueryData(queryKey, data),
  })
}

// The review dialog's "Create Rule" action - separate from a plain row
// category update (see ReviewDialog.tsx). Also invalidates the rules list
// so the Rules page reflects the newly created rule if it's open elsewhere.
function useCreateRuleFromBatch(kind: BatchKind, batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RuleQuickCreateRequest) =>
      api.post<StagingRuleCreateResult | RecategorizeRuleCreateResult>(`${batchUrl(kind, batchId)}/rules`, body),
    onSuccess: (data) => {
      qc.setQueryData([batchQueryKey(kind), 'current'], data.batch)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

function useUndoRuleFromBatch(kind: BatchKind, batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: BatchRuleUndoRequest) =>
      api.post<StagingBatch | RecategorizeBatch>(`${batchUrl(kind, batchId)}/rules/undo`, body),
    onSuccess: (data) => {
      qc.setQueryData([batchQueryKey(kind), 'current'], data)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

// "96 committed · 8 duplicates skipped · 2 refund pairs matched" - only a
// staging commit has duplicates/provisioning/refund-pairing to report; a
// recategorize commit's result is just the one count.
function commitToastText(kind: BatchKind, data: CommitResult | RecategorizeCommitResult): string {
  if (kind === 'recategorize') {
    const n = data.transactions_committed
    return `${n} transaction${n === 1 ? '' : 's'} updated.`
  }
  const d = data as CommitResult
  const parts = [`${d.transactions_committed} committed`]
  if (d.duplicates_skipped > 0) parts.push(`${d.duplicates_skipped} duplicate${d.duplicates_skipped === 1 ? '' : 's'} skipped`)
  if (d.refund_pairs_created > 0) parts.push(`${d.refund_pairs_created} refund pair${d.refund_pairs_created === 1 ? '' : 's'} matched`)
  return parts.join(' · ')
}

function useCommitPendingBatch(kind: BatchKind) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (batchId: string) => api.post<CommitResult | RecategorizeCommitResult>(`${batchUrl(kind, batchId)}/commit`),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['monthly-totals'] })
      qc.invalidateQueries({ queryKey: [batchQueryKey(kind)] })
      // Only an upload can provision a new account - a recategorize commit
      // never touches the accounts table.
      if (kind === 'staging') qc.invalidateQueries({ queryKey: ['accounts'] })
      toast.success(commitToastText(kind, data))
    },
    onError: (err) => toast.error(errMsg(err, 'Commit failed. Nothing was changed.')),
  })
}

function useDiscardPendingBatch(kind: BatchKind) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (batchId: string) => api.delete(batchUrl(kind, batchId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: [batchQueryKey(kind)] })
      toast.success(kind === 'staging' ? 'Batch discarded.' : 'Recategorization discarded.')
    },
    onError: (err) => toast.error(errMsg(err, 'Discard failed.')),
  })
}

function useCancelAiJob(kind: BatchKind) {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (batchId: string) => api.post<StagingBatch | RecategorizeBatch>(`${batchUrl(kind, batchId)}/ai/cancel`),
    onSuccess: (data) => {
      qc.setQueryData([batchQueryKey(kind), 'current'], data)
      toast.success('AI categorization cancelled.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't cancel AI categorization.")),
  })
}

export interface BatchActions {
  // No applyPending here - editing a row is optimistic now (REV-2 in
  // UI Review.dc.html), and each ReviewRowPopover field tracks its own
  // save status locally instead of the whole panel disabling on any one
  // row's in-flight request.
  applyRow: (key: number, body: BatchRowUpdateRequest) => Promise<void>
  createRule: (
    matchPattern: string,
    targetCategory: string,
    displayLabel: string | null,
  ) => Promise<{ rule_id: number; updated_rows: RuleRerunRowSnapshot[] }>
  createRulePending: boolean
  undoRule: (payload: BatchRuleUndoRequest) => Promise<void>
  undoRulePending: boolean
  commit: (batchId: string) => Promise<void>
  commitPending: boolean
  discard: (batchId: string) => Promise<void>
  discardPending: boolean
  cancelAi: (batchId: string) => Promise<void>
  cancelAiPending: boolean
}

// The one bundle of apply/createRule/undoRule/commit/discard callbacks plus
// their pending flags that a review dialog needs, regardless of which kind
// of PendingBatch it's showing.
export function useBatchActions(kind: BatchKind, batchId: string): BatchActions {
  const updateRow = useUpdateBatchRow(kind, batchId)
  const createRule = useCreateRuleFromBatch(kind, batchId)
  const undoRule = useUndoRuleFromBatch(kind, batchId)
  const commit = useCommitPendingBatch(kind)
  const discard = useDiscardPendingBatch(kind)
  const cancelAi = useCancelAiJob(kind)

  return {
    applyRow: (key, body) => updateRow.mutateAsync({ key, body }).then(() => {}),
    createRule: (matchPattern, targetCategory, displayLabel) =>
      createRule.mutateAsync({ match_pattern: matchPattern, target_category: targetCategory, display_label: displayLabel }),
    createRulePending: createRule.isPending,
    undoRule: (payload) => undoRule.mutateAsync(payload).then(() => {}),
    undoRulePending: undoRule.isPending,
    commit: (id) => commit.mutateAsync(id).then(() => {}),
    commitPending: commit.isPending,
    discard: (id) => discard.mutateAsync(id).then(() => {}),
    discardPending: discard.isPending,
    cancelAi: (id) => cancelAi.mutateAsync(id).then(() => {}),
    cancelAiPending: cancelAi.isPending,
  }
}

// --- contacts -----------------------------------------------------------------

export function useContacts() {
  return useQuery({ queryKey: ['contacts'], queryFn: () => api.get<Contact[]>('/contacts') })
}

export function useCreateContact() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (body: ContactCreateRequest) => api.post<Contact>('/contacts', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contacts'] })
      toast.success('Contact saved.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't save the contact.")),
  })
}

export function useUpdateContact() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ContactUpdateRequest }) =>
      api.patch<Contact>(`/contacts/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contacts'] })
      toast.success('Contact updated.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't update the contact.")),
  })
}

export function useDeleteContact() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/contacts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['contacts'] })
      toast.success('Contact deleted.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't delete the contact.")),
  })
}

export function useImportContactsCsv() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (file: File) => api.upload<ContactImportResult>('/contacts/import', file),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['contacts'] })
      toast.success(`Imported ${data.contacts_created} new contact(s), updated ${data.contacts_updated}.`)
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't import that CSV.")),
  })
}

// --- rules ----------------------------------------------------------------------

export function useRules(includeDefault = false) {
  return useQuery({
    queryKey: ['rules', includeDefault],
    queryFn: () => api.get<Rule[]>('/rules', { include_default: includeDefault }),
  })
}

// Backs the review dialog's "matches N transactions in history" live count
// (REV-5 in UI Review.dc.html) - the caller is expected to debounce
// `pattern` itself (see ReviewDialog.tsx), not on every keystroke.
export function useRuleMatchCount(pattern: string) {
  return useQuery({
    queryKey: ['rule-match-count', pattern],
    queryFn: () => api.get<MatchCount>('/rules/match-count', { pattern }),
    enabled: pattern.trim().length > 0,
    staleTime: 10_000,
  })
}

export function useCreateRule() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (body: RuleCreateRequest) => api.post<Rule>('/rules', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rules'] })
      toast.success('Rule saved.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't save the rule.")),
  })
}

export function useUpdateRule() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: RuleUpdateRequest }) => api.patch<Rule>(`/rules/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['rules'] })
      toast.success('Rule updated.')
    },
    onError: (err) => toast.error(errMsg(err, "Couldn't update the rule.")),
  })
}

export function useDeleteRule() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/rules/${id}`),
    // No success toast here - the delete itself fires 6 seconds after the
    // user clicks Delete (see Rules.tsx's undo window, X-2 in
    // UI Review.dc.html), and that click already got its own "Rule deleted
    // - Undo" toast immediately. A second toast when the deferred request
    // actually lands would be redundant noise for something the user
    // already confirmed. A failure still needs to surface, though - it's
    // the one case the optimistic removal turns out to have been wrong.
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
    onError: (err) => toast.error(errMsg(err, "Couldn't delete the rule.")),
  })
}

export function useReorderRules() {
  const qc = useQueryClient()
  const toast = useToast()
  // Rules.tsx only ever calls useRules() (includeDefault=false) - that's
  // the one cache entry a drag-and-drop reorder there needs to feel
  // instant. useRules(true) (DefaultRules.tsx) is reconciled via the
  // plain invalidate in onSuccess instead, since default rules are never
  // reorderable and don't need an optimistic path.
  const queryKey = ['rules', false] as const
  return useMutation({
    mutationFn: (orderedIds: number[]) => api.post<Rule[]>('/rules/reorder', { ordered_ids: orderedIds }),
    onMutate: async (orderedIds) => {
      await qc.cancelQueries({ queryKey })
      const previous = qc.getQueryData<Rule[]>(queryKey)
      if (previous) {
        const byId = new Map(previous.map((r) => [r.id, r]))
        // Priorities reassigned 1..N to mirror reorder_rules' own
        // enumerate(..., start=1) exactly, so the priority badge shown
        // during the round trip already matches what the server will
        // actually save (X-2's "list re-jumps" complaint was this exact
        // gap - before, the UI just showed the pre-drop order until the
        // response came back, then jumped to the real one).
        const next = orderedIds
          .map((id, i) => {
            const rule = byId.get(id)
            return rule ? { ...rule, priority: i + 1 } : null
          })
          .filter((r): r is Rule => r != null)
        qc.setQueryData(queryKey, next)
      }
      return { previous }
    },
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(queryKey, context.previous)
      toast.error(errMsg(err, "Couldn't save the new rule order - it's been reset."))
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

// --- categories -----------------------------------------------------------------

export function useCategories(includeHidden = false) {
  return useQuery({
    queryKey: ['categories', includeHidden],
    queryFn: () => api.get<Category[]>('/categories', { include_hidden: includeHidden }),
  })
}

// --- settings ---------------------------------------------------------------------

export function useSettings() {
  return useQuery({ queryKey: ['settings'], queryFn: () => api.get<Settings>('/settings') })
}

// AI provider configuration lives under its own /api/ai prefix, not nested
// under /api/settings/*.
export function useAiStatus(enabled: boolean) {
  return useQuery({
    queryKey: ['ai-status'],
    queryFn: () => api.get<AiStatus>('/ai/status'),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

// No onError toast here - SET-1 in UI Review.dc.html is explicit that a
// failed save shows its error inline under the checkbox (AiSection already
// renders updateAi.isError), not in a corner toast on top of that.
export function useUpdateAiSettings() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (body: AiSettingsUpdateRequest) => api.patch<AiSettings>('/ai', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['ai-status'] })
      toast.success('AI settings saved.')
    },
  })
}

// Checks reachability for whatever's currently typed into the AI section's
// fields, without saving them first (SET-4 in UI Review.dc.html) - a plain
// mutation, not a query, since it's fired on demand from a button click with
// a draft body that isn't cached anywhere. Reachable/unreachable renders
// inline from the mutation's own data/error, the same as the existing
// Recheck-connection status pill - no toast, for the same reason.
export function useTestAiSettings() {
  return useMutation({
    mutationFn: (body: AiSettingsUpdateRequest) => api.post<AiStatus>('/ai/test', body),
  })
}

// Data lifecycle (relocate/reset/scoped deletes) lives under its own
// /api/data-lifecycle prefix, not nested under /api/settings/*. Validated
// on blur by the Relocate modal (SET-6) - renders inline next to the field,
// not as a toast.
export function useCheckPath() {
  return useMutation({
    mutationFn: (path: string) => api.post<PathCheckResult>('/data-lifecycle/check-path', { path }),
  })
}

// No onError toast on any of the five mutations below - each caller
// (RelocateModal/ScopedDeleteModal/NuclearResetModal in Settings.tsx)
// already renders its own inline "Could not ___. Please try again." on
// mutation.isError, and stacking a toast on top of that would just repeat
// the same failure twice (the established rule from Batch 2 - see
// docs/ui-conventions.md). The success toasts are new (SET-3): the modal
// closes on success with no other confirmation, and DeleteScopeResult's
// count used to be fetched and silently discarded.
export function useRelocateDb() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (newPath: string) => api.post<Settings>('/data-lifecycle/relocate', { new_path: newPath }),
    onSuccess: (data) => {
      qc.setQueryData(['settings'], data)
      toast.success('Database relocated.')
    },
  })
}

export function useResetDb() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (confirm: string) => api.post('/data-lifecycle/reset', { confirm }),
    onSuccess: () => {
      qc.invalidateQueries()
      toast.success('Everything has been reset.')
    },
  })
}

export function useDeleteAllRules() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-rules', { confirm }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['rules'] })
      toast.success(`${data.deleted_count} rule${data.deleted_count === 1 ? '' : 's'} deleted.`)
    },
  })
}

export function useDeleteAllContacts() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-contacts', { confirm }),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['contacts'] })
      toast.success(`${data.deleted_count} contact${data.deleted_count === 1 ? '' : 's'} deleted.`)
    },
  })
}

export function useDeleteAllTransactions() {
  const qc = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-transactions', { confirm }),
    onSuccess: (data) => {
      qc.invalidateQueries()
      toast.success(`${data.deleted_count} transaction${data.deleted_count === 1 ? '' : 's'} deleted.`)
    },
  })
}
