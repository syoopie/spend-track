from pydantic import BaseModel


class StagingAccountOut(BaseModel):
    bank_name: str
    account_number_masked: str
    account_type: str
    is_new: bool


class StagingRowOut(BaseModel):
    index: int
    account_number_masked: str
    transaction_date: str
    raw_description: str
    amount: float
    category: str
    subcategory: str | None
    is_excluded: bool
    exclusion_reason: str | None
    contact_id: int | None
    needs_review: bool
    is_duplicate: bool


class StagingBatchOut(BaseModel):
    batch_id: str
    source_filename: str
    bank_name: str
    accounts: list[StagingAccountOut]
    rows: list[StagingRowOut]
    new_extracted: int
    duplicates_skipped: int
    new_accounts_provisioned: int
    needs_category_count: int


class StagingRowUpdateRequest(BaseModel):
    category: str
    subcategory: str | None = None
    save_as_rule: bool = False
    rule_pattern: str | None = None
    rule_priority: int | None = None
    save_as_contact: bool = False
    contact_name: str | None = None
    contact_identifier: str | None = None


class CommitResult(BaseModel):
    transactions_committed: int
    duplicates_skipped: int
    accounts_provisioned: int
    refund_pairs_created: int


class ErrorDetail(BaseModel):
    code: str
    message: str


class AccountOut(BaseModel):
    id: str
    bank_name: str
    account_number_masked: str
    account_type: str


class TransactionOut(BaseModel):
    id: int
    account_id: str
    bank_name: str
    account_number_masked: str
    transaction_date: str
    raw_description: str
    cleaned_description: str | None
    amount: float
    category: str
    subcategory: str | None
    contact_id: int | None
    is_excluded: bool
    exclusion_reason: str | None
    has_refund_link: bool


class RefundPairingOut(BaseModel):
    original: TransactionOut
    refund: TransactionOut


class ContactIdentifierIn(BaseModel):
    identifier: str


class ContactCreateRequest(BaseModel):
    name: str
    default_category: str
    default_subcategory: str | None = None
    identifiers: list[str] = []


class ContactUpdateRequest(BaseModel):
    name: str | None = None
    default_category: str | None = None
    default_subcategory: str | None = None
    identifiers: list[str] | None = None  # if provided, replaces the full identifier set


class ContactOut(BaseModel):
    id: int
    name: str
    default_category: str
    default_subcategory: str | None
    identifiers: list[str]
    historical_spend: float


class ContactImportResult(BaseModel):
    contacts_created: int
    contacts_updated: int


class RuleCreateRequest(BaseModel):
    priority: int | None = None
    match_pattern: str
    target_category: str | None = None
    target_subcategory: str | None = None
    is_exclusion_rule: bool = False
    exclusion_reason: str | None = None


class RuleUpdateRequest(BaseModel):
    priority: int | None = None
    match_pattern: str | None = None
    target_category: str | None = None
    target_subcategory: str | None = None
    is_exclusion_rule: bool | None = None
    exclusion_reason: str | None = None


class RuleOut(BaseModel):
    id: int
    priority: int
    match_pattern: str
    target_category: str | None
    target_subcategory: str | None
    is_exclusion_rule: bool
    exclusion_reason: str | None


class RuleReorderRequest(BaseModel):
    ordered_ids: list[int]  # new top-to-bottom order; priorities are reassigned 1..N


class CategoryCreateRequest(BaseModel):
    name: str
    hue: int | None = None


class CategoryOut(BaseModel):
    id: int
    name: str
    hue: int | None
    sort_order: int


class SettingsOut(BaseModel):
    db_path: str
    size_bytes: int
    schema_version: int


class RelocateRequest(BaseModel):
    new_path: str


class ResetRequest(BaseModel):
    confirm: str


class MetricCards(BaseModel):
    net_expenditure: float
    total_inflow: float
    total_outflow: float
    paynow_total: float
    card_total: float
    paynow_pct: float
    card_pct: float


class CashFlowMonth(BaseModel):
    month: str
    inflow: float
    outflow: float


class CategoryBreakdownSlice(BaseModel):
    category: str
    amount: float
    pct: float


class VelocityPoint(BaseModel):
    day: int
    current_month_cumulative: float
    previous_month_cumulative: float


class TopEntry(BaseModel):
    name: str
    amount: float


class DashboardSummaryOut(BaseModel):
    month: str
    metrics: MetricCards
    cash_flow: list[CashFlowMonth]
    category_breakdown: list[CategoryBreakdownSlice]
    spend_velocity: list[VelocityPoint]
    top_merchants: list[TopEntry]
    top_paynow_contacts: list[TopEntry]
