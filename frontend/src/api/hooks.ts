import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from './client'
import type {
  Account,
  AiSettings,
  AiSettingsUpdateRequest,
  AiStatus,
  BatchRowUpdateRequest,
  BatchRuleUndoRequest,
  CommitResult,
  Contact,
  ContactCreateRequest,
  ContactImportResult,
  ContactUpdateRequest,
  DashboardSummary,
  DeleteScopeResult,
  MonthlyTotal,
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
  StagingBatch,
  StagingRuleCreateResult,
  Transaction,
  TransactionUpdateRequest,
  Category,
} from './types'

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
  })
}

export function useUpdateTransaction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: TransactionUpdateRequest }) =>
      api.patch<Transaction>(`/transactions/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
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
  })
}

export function useMonthlyTotals(accountId?: string) {
  return useQuery({
    queryKey: ['monthly-totals', accountId],
    queryFn: () => api.get<MonthlyTotal[]>('/dashboard/monthly-totals', { account_id: accountId }),
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

function useUpdateBatchRow(kind: BatchKind, batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ key, body }: { key: number; body: BatchRowUpdateRequest }) =>
      api.patch<StagingBatch | RecategorizeBatch>(`${batchUrl(kind, batchId)}/rows/${key}`, body),
    onSuccess: (data) => qc.setQueryData([batchQueryKey(kind), 'current'], data),
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

function useCommitPendingBatch(kind: BatchKind) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.post<CommitResult | RecategorizeCommitResult>(`${batchUrl(kind, batchId)}/commit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['monthly-totals'] })
      qc.invalidateQueries({ queryKey: [batchQueryKey(kind)] })
      // Only an upload can provision a new account - a recategorize commit
      // never touches the accounts table.
      if (kind === 'staging') qc.invalidateQueries({ queryKey: ['accounts'] })
    },
  })
}

function useDiscardPendingBatch(kind: BatchKind) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.delete(batchUrl(kind, batchId)),
    onSuccess: () => qc.invalidateQueries({ queryKey: [batchQueryKey(kind)] }),
  })
}

export interface BatchActions {
  applyRow: (key: number, body: BatchRowUpdateRequest) => Promise<void>
  applyPending: boolean
  createRule: (matchPattern: string, targetCategory: string) => Promise<{ rule_id: number; updated_rows: RuleRerunRowSnapshot[] }>
  createRulePending: boolean
  undoRule: (payload: BatchRuleUndoRequest) => Promise<void>
  undoRulePending: boolean
  commit: (batchId: string) => Promise<void>
  commitPending: boolean
  discard: (batchId: string) => Promise<void>
  discardPending: boolean
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

  return {
    applyRow: (key, body) => updateRow.mutateAsync({ key, body }).then(() => {}),
    applyPending: updateRow.isPending,
    createRule: (matchPattern, targetCategory) =>
      createRule.mutateAsync({ match_pattern: matchPattern, target_category: targetCategory }),
    createRulePending: createRule.isPending,
    undoRule: (payload) => undoRule.mutateAsync(payload).then(() => {}),
    undoRulePending: undoRule.isPending,
    commit: (id) => commit.mutateAsync(id).then(() => {}),
    commitPending: commit.isPending,
    discard: (id) => discard.mutateAsync(id).then(() => {}),
    discardPending: discard.isPending,
  }
}

// --- contacts -----------------------------------------------------------------

export function useContacts() {
  return useQuery({ queryKey: ['contacts'], queryFn: () => api.get<Contact[]>('/contacts') })
}

export function useCreateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: ContactCreateRequest) => api.post<Contact>('/contacts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useUpdateContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: ContactUpdateRequest }) =>
      api.patch<Contact>(`/contacts/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useDeleteContact() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/contacts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useImportContactsCsv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => api.upload<ContactImportResult>('/contacts/import', file),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

// --- rules ----------------------------------------------------------------------

export function useRules(includeDefault = false) {
  return useQuery({
    queryKey: ['rules', includeDefault],
    queryFn: () => api.get<Rule[]>('/rules', { include_default: includeDefault }),
  })
}

export function useCreateRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RuleCreateRequest) => api.post<Rule>('/rules', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

export function useUpdateRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: RuleUpdateRequest }) => api.patch<Rule>(`/rules/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

export function useDeleteRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.delete(`/rules/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

export function useReorderRules() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (orderedIds: number[]) => api.post<Rule[]>('/rules/reorder', { ordered_ids: orderedIds }),
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

export function useUpdateAiSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AiSettingsUpdateRequest) => api.patch<AiSettings>('/ai', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['ai-status'] })
    },
  })
}

// Data lifecycle (relocate/reset/scoped deletes) lives under its own
// /api/data-lifecycle prefix, not nested under /api/settings/*.
export function useRelocateDb() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (newPath: string) => api.post<Settings>('/data-lifecycle/relocate', { new_path: newPath }),
    onSuccess: (data) => qc.setQueryData(['settings'], data),
  })
}

export function useResetDb() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post('/data-lifecycle/reset', { confirm }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useDeleteAllRules() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-rules', { confirm }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

export function useDeleteAllContacts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-contacts', { confirm }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useDeleteAllTransactions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/data-lifecycle/delete-transactions', { confirm }),
    onSuccess: () => qc.invalidateQueries(),
  })
}
