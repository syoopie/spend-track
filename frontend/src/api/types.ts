export interface StagingAccount {
  bank_name: string
  account_number_masked: string
  account_type: string
  is_new: boolean
}

// Shared row shape for both a staging batch and a recategorize batch
// (previously StagingRow/RecategorizeRow, identical fields under different
// key names: `index` vs `transaction_id`) - `key` is whichever one applies,
// matching the backend's BatchRowOut. A recategorize row's is_duplicate is
// always false - dedup only applies to newly-parsed staging rows. Unifying
// this is what lets components/ReviewDialog.tsx and useBatchActions() treat
// both kinds of batch identically.
export interface BatchRow {
  key: number
  account_number_masked: string
  transaction_date: string
  raw_description: string
  matched_label: string | null
  amount: number
  category: string
  subcategory: string | null
  is_excluded: boolean
  exclusion_reason: string | null
  contact_id: number | null
  needs_review: boolean
  is_duplicate: boolean
  is_paynow: boolean
  original_category: string
  original_label: string | null
  ai_suggested: boolean
  ai_category: string | null
  ai_label: string | null
  ai_rule_pattern: string | null
}

export type AiJobStatus = 'disabled' | 'running' | 'done' | 'failed' | 'cancelled'

export interface StagingBatch {
  batch_id: string
  created_at: string
  source_filenames: string[]
  bank_name: string
  accounts: StagingAccount[]
  rows: BatchRow[]
  new_extracted: number
  duplicates_skipped: number
  new_accounts_provisioned: number
  needs_category_count: number
  ai_status: AiJobStatus
  ai_warning: string | null
  ai_model: string | null
  ai_started_at: string | null
  ai_suggested_count: number
}

// Shared request body for editing one row of either a staging batch or a
// recategorize batch (previously StagingRowUpdateRequest/
// RecategorizeRowUpdateRequest, identical fields under different names).
export interface BatchRowUpdateRequest {
  category: string
  matched_label?: string | null
  subcategory?: string | null
  save_as_rule?: boolean
  rule_pattern?: string | null
  rule_priority?: number | null
  save_as_contact?: boolean
  contact_name?: string | null
  contact_identifier?: string | null
  restore_default?: boolean
}

// The "Create Rule" action's own request/response shape - deliberately
// separate from StagingRowUpdateRequest's save_as_rule flag (see
// ReviewDialog.tsx): applying a category to one row and creating a
// persistent rule from it are two distinct actions with two distinct
// outcomes, not one checkbox bolted onto Apply.
export interface RuleQuickCreateRequest {
  match_pattern: string
  target_category: string
  target_subcategory?: string | null
  display_label?: string | null
}

// Both directions of a rule-rerun's row diff - the server returns one of
// these per row a newly created rule changed (holding that row's *previous*
// values, so the frontend can offer an undo), and the same shape is echoed
// straight back to the undo endpoint to restore it.
export interface RuleRerunRowSnapshot {
  key: number
  category: string
  subcategory: string | null
  matched_label: string | null
  is_excluded: boolean
  exclusion_reason: string | null
  contact_id: number | null
  needs_review: boolean
}

export interface StagingRuleCreateResult {
  rule_id: number
  updated_rows: RuleRerunRowSnapshot[]
  batch: StagingBatch
}

// Shared request body for undoing a rule-create action against either kind
// of batch (previously StagingRuleUndoRequest/RecategorizeRuleUndoRequest,
// identical fields under different names).
export interface BatchRuleUndoRequest {
  rule_id: number
  rows: RuleRerunRowSnapshot[]
}

export interface CommitResult {
  transactions_committed: number
  duplicates_skipped: number
  accounts_provisioned: number
  refund_pairs_created: number
}

export interface Account {
  id: string
  bank_name: string
  account_number_masked: string
  account_type: string
}

export interface Transaction {
  id: number
  account_id: string
  bank_name: string
  account_number_masked: string
  transaction_date: string
  raw_description: string
  cleaned_description: string | null
  matched_label: string | null
  amount: number
  category: string
  subcategory: string | null
  contact_id: number | null
  is_excluded: boolean
  exclusion_reason: string | null
  has_refund_link: boolean
  source_filename: string | null
}

export interface SourceFileSummary {
  filename: string
  transaction_count: number
}

export interface TransactionUpdateRequest {
  category?: string
  subcategory?: string | null
  matched_label?: string | null
  contact_id?: number | null
  is_excluded?: boolean
  exclusion_reason?: string | null
}

export interface RecategorizeRequest {
  date_from: string
  date_to: string
  account_id?: string | null
}

export interface RecategorizeBatch {
  batch_id: string
  date_from: string
  date_to: string
  account_id: string | null
  scanned: number
  changed: number
  rows: BatchRow[]
  ai_status: AiJobStatus
  ai_warning: string | null
  ai_model: string | null
  ai_started_at: string | null
  ai_suggested_count: number
}

export interface RecategorizeRuleCreateResult {
  rule_id: number
  updated_rows: RuleRerunRowSnapshot[]
  batch: RecategorizeBatch
}

export interface RecategorizeCommitResult {
  transactions_committed: number
}

export interface RefundPairing {
  original: Transaction
  refund: Transaction
}

export interface Contact {
  id: number
  name: string
  // Independently optional - a contact who's only ever paid, or only ever
  // pays, has no reason to carry a default for the direction that never
  // happens (see backend/src/app/schema.sql's contacts table).
  default_category_outflow: string | null
  default_category_inflow: string | null
  default_subcategory: string | null
  identifiers: string[]
  historical_spend: number
}

export interface ContactCreateRequest {
  name: string
  default_category_outflow?: string | null
  default_category_inflow?: string | null
  default_subcategory?: string | null
  identifiers: string[]
}

export interface ContactUpdateRequest {
  name?: string
  default_category_outflow?: string | null
  default_category_inflow?: string | null
  default_subcategory?: string | null
  identifiers?: string[]
  // default_category_outflow/inflow above already use undefined/None for
  // "leave unchanged" (matching every other field here), so there's no way
  // to ask for an explicit no-selection without a separate signal - see
  // ContactUpdateRequest's docstring on the backend (models.py).
  clear_default_category_outflow?: boolean
  clear_default_category_inflow?: boolean
}

export interface ContactImportResult {
  contacts_created: number
  contacts_updated: number
}

export interface Rule {
  id: number
  priority: number
  match_pattern: string
  target_category: string | null
  target_subcategory: string | null
  is_exclusion_rule: boolean
  exclusion_reason: string | null
  // The one transaction direction this rule can ever match - a category
  // rule's is always the same as its own target_category (the backend
  // keeps them in sync), an exclusion rule's is independently chosen since
  // it has no category to imply one.
  direction: CategoryDirection
  is_default: boolean
  display_label: string | null
}

export interface MatchCount {
  count: number
}

export interface RuleCreateRequest {
  priority?: number | null
  match_pattern: string
  target_category?: string | null
  target_subcategory?: string | null
  is_exclusion_rule?: boolean
  exclusion_reason?: string | null
  // Optional for a category rule (the backend derives it from
  // target_category) - required in practice for an exclusion rule, which
  // has nothing else to derive it from.
  direction?: CategoryDirection | null
  // Meaningless (and ignored by the backend) for an exclusion rule.
  display_label?: string | null
}

export interface RuleUpdateRequest {
  priority?: number | null
  match_pattern?: string
  target_category?: string | null
  target_subcategory?: string | null
  is_exclusion_rule?: boolean
  exclusion_reason?: string | null
  direction?: CategoryDirection | null
  display_label?: string | null
}

export type CategoryDirection = 'inflow' | 'outflow'

export interface Category {
  id: number
  name: string
  hue: number | null
  icon: string | null
  is_hidden: boolean
  sort_order: number
  direction: CategoryDirection
}

export type AiProviderKind = 'ollama' | 'openai_compatible' | 'anthropic'

export interface AiSettingsFields {
  ai_enabled: boolean
  ai_provider: AiProviderKind
  ollama_url: string
  ollama_model: string
  openai_base_url: string
  openai_model: string
  openai_api_key_set: boolean
  openai_api_key_last4: string | null
  anthropic_model: string
  anthropic_api_key_set: boolean
  anthropic_api_key_last4: string | null
}

export type AiSettings = AiSettingsFields

export interface AiSettingsUpdateRequest {
  ai_enabled?: boolean
  ai_provider?: AiProviderKind
  ollama_url?: string
  ollama_model?: string
  openai_base_url?: string
  openai_model?: string
  openai_api_key?: string
  clear_openai_api_key?: boolean
  anthropic_model?: string
  anthropic_api_key?: string
  clear_anthropic_api_key?: boolean
}

export interface AiStatus {
  reachable: boolean
  models: string[]
  error: string | null
}

export interface PathCheckResult {
  valid: boolean
  resolved_path: string
  free_bytes: number | null
  error: string | null
}

export interface Settings extends AiSettingsFields {
  db_path: string
  size_bytes: number
  schema_version: number
  country_code: string
  country_name: string
  currency_code: string
  currency_symbol: string
  transfer_scheme_name: string
  /** Banks whose statements actually parse today. */
  supported_banks: string[]
  /** Banks recognized on upload but not parsed yet. */
  detected_banks: string[]
}

export interface DeleteScopeResult {
  deleted_count: number
}

export interface MetricCards {
  net_expenditure: number
  total_inflow: number
  total_outflow: number
}

export interface CashFlowMonth {
  month: string
  inflow: number
  outflow: number
}

export interface MonthlyTotal {
  month: string
  inflow: number
  outflow: number
}

export interface CategoryBreakdownSlice {
  category: string
  amount: number
  pct: number
}

export interface VelocityPoint {
  day: number
  date: string
  current_period_cumulative: number
  previous_period_cumulative: number
}

export interface TopEntry {
  name: string
  amount: number
}

export interface DashboardSummary {
  date_from: string
  date_to: string
  metrics: MetricCards
  cash_flow: CashFlowMonth[]
  category_breakdown: CategoryBreakdownSlice[]
  spend_velocity: VelocityPoint[]
  top_merchants: TopEntry[]
  top_paynow_contacts: TopEntry[]
}

export interface ApiErrorBody {
  code: string
  message: string
}
