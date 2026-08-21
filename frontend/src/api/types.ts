export interface StagingAccount {
  bank_name: string
  account_number_masked: string
  account_type: string
  is_new: boolean
}

export interface StagingRow {
  index: number
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
}

export interface StagingBatch {
  batch_id: string
  source_filename: string
  bank_name: string
  accounts: StagingAccount[]
  rows: StagingRow[]
  new_extracted: number
  duplicates_skipped: number
  new_accounts_provisioned: number
  needs_category_count: number
}

export interface StagingRowUpdateRequest {
  category: string
  subcategory?: string | null
  save_as_rule?: boolean
  rule_pattern?: string | null
  rule_priority?: number | null
  save_as_contact?: boolean
  contact_name?: string | null
  contact_identifier?: string | null
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

export interface RecategorizeResult {
  transactions_scanned: number
  transactions_changed: number
}

export interface RefundPairing {
  original: Transaction
  refund: Transaction
}

export interface Contact {
  id: number
  name: string
  default_category: string
  default_subcategory: string | null
  identifiers: string[]
  historical_spend: number
}

export interface ContactCreateRequest {
  name: string
  default_category: string
  default_subcategory?: string | null
  identifiers: string[]
}

export interface ContactUpdateRequest {
  name?: string
  default_category?: string
  default_subcategory?: string | null
  identifiers?: string[]
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
  is_default: boolean
  display_label: string | null
}

export interface RuleCreateRequest {
  priority?: number | null
  match_pattern: string
  target_category?: string | null
  target_subcategory?: string | null
  is_exclusion_rule?: boolean
  exclusion_reason?: string | null
}

export interface Category {
  id: number
  name: string
  hue: number | null
  icon: string | null
  is_hidden: boolean
  sort_order: number
}

export interface Settings {
  db_path: string
  size_bytes: number
  schema_version: number
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
  current_month_cumulative: number
  previous_month_cumulative: number
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
