import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from './client'
import type {
  Account,
  CommitResult,
  Contact,
  ContactCreateRequest,
  ContactImportResult,
  ContactUpdateRequest,
  DashboardSummary,
  MonthlyTotal,
  RecategorizeRequest,
  RecategorizeResult,
  RefundPairing,
  Rule,
  RuleCreateRequest,
  Settings,
  StagingBatch,
  StagingRowUpdateRequest,
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

export function useRecategorizeTransactions() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: RecategorizeRequest) => api.post<RecategorizeResult>('/transactions/recategorize', body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
      qc.invalidateQueries({ queryKey: ['monthly-totals'] })
    },
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

export function useCommitBatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (batchId: string) => api.post<CommitResult>(`/statements/staging/${batchId}/commit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      qc.invalidateQueries({ queryKey: ['transactions'] })
      qc.invalidateQueries({ queryKey: ['dashboard-summary'] })
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
