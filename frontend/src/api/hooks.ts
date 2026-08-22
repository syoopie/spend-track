import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from './client'
import type {
  Account,
  AiSettings,
  AiSettingsUpdateRequest,
  AiStatus,
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
  RecategorizeRowUpdateRequest,
  RecategorizeRuleCreateResult,
  RecategorizeRuleUndoRequest,
  RefundPairing,
  Rule,
  RuleCreateRequest,
  RuleQuickCreateRequest,
  RuleUpdateRequest,
  Settings,
  StagingBatch,
  StagingRowUpdateRequest,
  StagingRuleCreateResult,
  StagingRuleUndoRequest,
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

export function useUpdateRecategorizeRow(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ transactionId, body }: { transactionId: number; body: RecategorizeRowUpdateRequest }) =>
      api.patch<RecategorizeBatch>(`/transactions/recategorize/${batchId}/rows/${transactionId}`, body),
    onSuccess: (data) => qc.setQueryData(['recategorize-batch', 'current'], data),
  })
}

// The review dialog's "Create Rule" action - separate from a plain row
// category update (see ReviewDialog.tsx and StagingRuleCreateResult's own
// comment in types.ts). Also invalidates the rules list so the Rules page
// reflects the newly created rule if it's open in another tab.
export function useCreateRuleFromRecategorizeBatch(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RuleQuickCreateRequest) =>
      api.post<RecategorizeRuleCreateResult>(`/transactions/recategorize/${batchId}/rules`, body),
    onSuccess: (data) => {
      qc.setQueryData(['recategorize-batch', 'current'], data.batch)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useUndoRuleFromRecategorizeBatch(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RecategorizeRuleUndoRequest) =>
      api.post<RecategorizeBatch>(`/transactions/recategorize/${batchId}/rules/undo`, body),
    onSuccess: (data) => {
      qc.setQueryData(['recategorize-batch', 'current'], data)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useCommitRecategorizeBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.post<RecategorizeCommitResult>(`/transactions/recategorize/${batchId}/commit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['monthly-totals'] })
      qc.invalidateQueries({ queryKey: ['recategorize-batch'] })
    },
  })
}

export function useDiscardRecategorizeBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.delete(`/transactions/recategorize/${batchId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['recategorize-batch'] }),
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

export function useUpdateStagingRow(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ index, body }: { index: number; body: StagingRowUpdateRequest }) =>
      api.patch<StagingBatch>(`/statements/staging/${batchId}/rows/${index}`, body),
    onSuccess: (data) => qc.setQueryData(['staging-batch', 'current'], data),
  })
}

export function useCreateRuleFromStagingBatch(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RuleQuickCreateRequest) =>
      api.post<StagingRuleCreateResult>(`/statements/staging/${batchId}/rules`, body),
    onSuccess: (data) => {
      qc.setQueryData(['staging-batch', 'current'], data.batch)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useUndoRuleFromStagingBatch(batchId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: StagingRuleUndoRequest) => api.post<StagingBatch>(`/statements/staging/${batchId}/rules/undo`, body),
    onSuccess: (data) => {
      qc.setQueryData(['staging-batch', 'current'], data)
      qc.invalidateQueries({ queryKey: ['rules'] })
    },
  })
}

export function useCommitBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.post<CommitResult>(`/statements/staging/${batchId}/commit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['monthly-totals'] })
      qc.invalidateQueries({ queryKey: ['staging-batch'] })
    },
  })
}

export function useDiscardBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.delete(`/statements/staging/${batchId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staging-batch'] }),
  })
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

export function useAiStatus(enabled: boolean) {
  return useQuery({
    queryKey: ['ai-status'],
    queryFn: () => api.get<AiStatus>('/settings/ai/status'),
    enabled,
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateAiSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: AiSettingsUpdateRequest) => api.patch<AiSettings>('/settings/ai', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      qc.invalidateQueries({ queryKey: ['ai-status'] })
    },
  })
}

export function useRelocateDb() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (newPath: string) => api.post<Settings>('/settings/relocate', { new_path: newPath }),
    onSuccess: (data) => qc.setQueryData(['settings'], data),
  })
}

export function useResetDb() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post('/settings/reset', { confirm }),
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useDeleteAllRules() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/settings/delete-rules', { confirm }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rules'] }),
  })
}

export function useDeleteAllContacts() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/settings/delete-contacts', { confirm }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['contacts'] }),
  })
}

export function useDeleteAllTransactions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (confirm: string) => api.post<DeleteScopeResult>('/settings/delete-transactions', { confirm }),
    onSuccess: () => qc.invalidateQueries(),
  })
}
