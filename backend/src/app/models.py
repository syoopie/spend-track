from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AiProviderKind = Literal["ollama", "openai_compatible", "anthropic"]


class StagingAccountOut(BaseModel):
    bank_name: str
    account_number_masked: str
    account_type: str
    is_new: bool
    is_card: bool


class BatchRowOut(BaseModel):
    """Shared row shape for both a staging batch (engine/staging_store.py)
    and a recategorize batch (engine/recategorize_job.py) - `key` is a
    StagingRow.index or a RecategorizeRow.transaction_id depending on which
    kind of batch this came from (same convention as RuleRerunRowSnapshot's
    own `key`). A recategorize row always has is_duplicate=False - dedup
    only applies to newly-parsed staging rows. Unifying this (previously
    StagingRowOut/RecategorizeRowOut) is what lets the frontend's
    ReviewDialog/BatchActions treat both kinds of batch identically."""

    key: int
    account_number_masked: str
    transaction_date: str
    raw_description: str
    matched_label: str | None
    amount: float
    category: str
    subcategory: str | None
    is_excluded: bool
    exclusion_reason: str | None
    contact_id: int | None
    needs_review: bool
    is_duplicate: bool
    is_paynow: bool
    # The rules/contact/PayNow engine's answer before any AI or manual edit -
    # what "Restore Default" falls back to when there's no ai_category to
    # prefer instead. See ReviewDialog.tsx.
    original_category: str
    original_label: str | None
    ai_suggested: bool
    ai_category: str | None
    ai_label: str | None
    ai_rule_pattern: str | None


class StagingBatchOut(BaseModel):
    batch_id: str
    created_at: datetime
    source_filenames: list[str]
    bank_name: str
    accounts: list[StagingAccountOut]
    rows: list[BatchRowOut]
    new_extracted: int
    duplicates_skipped: int
    new_accounts_provisioned: int
    needs_category_count: int
    ai_status: str
    ai_warning: str | None
    ai_model: str | None
    ai_started_at: datetime | None
    ai_suggested_count: int


class BatchRowUpdateRequest(BaseModel):
    """Shared request body for editing one row of either a staging batch or
    a recategorize batch (previously StagingRowUpdateRequest/
    RecategorizeRowUpdateRequest, identical fields under different names)."""

    category: str
    # The row's display name, editable directly like category - None means
    # "no custom label, show the raw bank description". Ignored (along with
    # category) when restore_default is set below.
    matched_label: str | None = None
    subcategory: str | None = None
    save_as_rule: bool = False
    rule_pattern: str | None = None
    rule_priority: int | None = None
    save_as_contact: bool = False
    contact_name: str | None = None
    contact_identifier: str | None = None
    # True only for the single "Restore Default" action (see
    # ReviewDialog.tsx) - ignores category/matched_label above and instead
    # re-applies the row's permanently-recorded ai_category/ai_label if an
    # AI suggestion exists, else its permanently-recorded
    # original_category/original_label (the rules engine's answer before any
    # AI or manual edit).
    restore_default: bool = False


class RuleQuickCreateRequest(BaseModel):
    """Body for the "Create Rule" action in the review dialogs - a
    deliberately narrower sibling of RuleCreateRequest (no priority/exclusion
    fields - a quick rule created mid-review is always a plain category
    rule, appended after the user's existing rules; exclusion rules are
    still only made via the full Rules page)."""

    match_pattern: str
    target_category: str
    target_subcategory: str | None = None
    # The label the row was showing when this rule was created (see
    # ReviewDialog.tsx's "Create a rule" section) - carried over so future
    # matches get the same clean display name, not just this one row's.
    display_label: str | None = None


class RuleRerunRowSnapshot(BaseModel):
    """Both directions of a rule-rerun's row diff: the server returns one of
    these per row a newly created rule changed (holding that row's *previous*
    values, for an undo prompt), and the client echoes the same list back
    verbatim to the undo endpoint to restore it. key is a StagingRow.index or
    a RecategorizeRow.transaction_id, matching whichever batch this came
    from."""

    key: int
    category: str
    subcategory: str | None
    matched_label: str | None
    is_excluded: bool
    exclusion_reason: str | None
    contact_id: int | None
    needs_review: bool


class StagingRuleCreateResult(BaseModel):
    rule_id: int
    updated_rows: list[RuleRerunRowSnapshot]
    batch: StagingBatchOut


class BatchRuleUndoRequest(BaseModel):
    """Shared request body for undoing a rule-create action against either
    kind of pending batch (previously StagingRuleUndoRequest/
    RecategorizeRuleUndoRequest, identical fields under different names)."""

    rule_id: int
    rows: list[RuleRerunRowSnapshot]


class CommitResult(BaseModel):
    transactions_committed: int
    duplicates_skipped: int
    accounts_provisioned: int
    refund_pairs_created: int


class AccountOut(BaseModel):
    id: str
    bank_name: str
    account_number_masked: str
    account_type: str
    is_card: bool


class TransactionOut(BaseModel):
    id: int
    account_id: str
    bank_name: str
    account_number_masked: str
    transaction_date: str
    raw_description: str
    cleaned_description: str | None
    matched_label: str | None
    amount: float
    category: str
    subcategory: str | None
    contact_id: int | None
    is_excluded: bool
    exclusion_reason: str | None
    has_refund_link: bool
    source_filename: str | None


class TransactionUpdateRequest(BaseModel):
    category: str | None = None
    subcategory: str | None = None
    matched_label: str | None = None
    contact_id: int | None = None
    is_excluded: bool | None = None
    exclusion_reason: str | None = None


class RefundPairingOut(BaseModel):
    original: TransactionOut
    refund: TransactionOut


class RecategorizeRequest(BaseModel):
    date_from: str  # YYYY-MM
    date_to: str  # YYYY-MM
    account_id: str | None = None


class RecategorizeBatchOut(BaseModel):
    batch_id: str
    date_from: str
    date_to: str
    account_id: str | None
    scanned: int
    changed: int
    rows: list[BatchRowOut]
    ai_status: str
    ai_warning: str | None
    ai_model: str | None
    ai_started_at: datetime | None
    ai_suggested_count: int


class RecategorizeRuleCreateResult(BaseModel):
    """Mirrors StagingRuleCreateResult exactly - see its docstring-level comment."""

    rule_id: int
    updated_rows: list[RuleRerunRowSnapshot]
    batch: RecategorizeBatchOut


class RecategorizeCommitResult(BaseModel):
    transactions_committed: int


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
    # Which transaction direction this rule can ever match. Optional because
    # a category-assigning rule's direction is fully implied by its own
    # target_category (the router derives it when omitted) - only an
    # exclusion rule, which has no real category to infer from, actually
    # needs this supplied explicitly.
    direction: Literal["inflow", "outflow"] | None = None
    # The display label a matching transaction gets, replacing the raw bank
    # description in the UI - same field a rule already carries in the DB
    # (engine/rules.py falls back to match_pattern.title() when this is
    # None). Meaningless for an exclusion rule, which never sets a label.
    display_label: str | None = None


class RuleUpdateRequest(BaseModel):
    priority: int | None = None
    match_pattern: str | None = None
    target_category: str | None = None
    target_subcategory: str | None = None
    is_exclusion_rule: bool | None = None
    exclusion_reason: str | None = None
    direction: Literal["inflow", "outflow"] | None = None
    # None here means "leave the stored value alone" (same convention as
    # every other optional field on this request) - clearing a label back to
    # "use match_pattern.title()" isn't wired up as a distinct action since
    # there's no ambiguity to resolve: retyping the pattern's own title-cased
    # text into this field does the same thing explicitly.
    display_label: str | None = None


class RuleOut(BaseModel):
    id: int
    priority: int
    match_pattern: str
    target_category: str | None
    target_subcategory: str | None
    is_exclusion_rule: bool
    exclusion_reason: str | None
    direction: Literal["inflow", "outflow"]
    is_default: bool
    display_label: str | None


class RuleReorderRequest(BaseModel):
    ordered_ids: list[int]  # new top-to-bottom order; priorities are reassigned 1..N


class MatchCountOut(BaseModel):
    count: int


class CategoryCreateRequest(BaseModel):
    name: str
    hue: int | None = None
    icon: str | None = None
    direction: str = "outflow"  # 'inflow' or 'outflow' - see schema.sql's categories.direction


class CategoryOut(BaseModel):
    id: int
    name: str
    hue: int | None
    icon: str | None
    is_hidden: bool
    sort_order: int
    direction: str


class SettingsOut(BaseModel):
    db_path: str
    size_bytes: int
    schema_version: int
    country_code: str
    country_name: str
    currency_code: str
    currency_symbol: str
    transfer_scheme_name: str
    #: Banks whose statements actually parse today.
    supported_banks: list[str]
    #: Banks recognized on upload but not parsed yet - reported so the UI can
    #: say "detected, not supported" instead of implying they work.
    detected_banks: list[str]
    ai_enabled: bool
    ai_provider: AiProviderKind
    ollama_url: str
    ollama_model: str
    openai_base_url: str
    openai_model: str
    openai_api_key_set: bool
    openai_api_key_last4: str | None
    anthropic_model: str
    anthropic_api_key_set: bool
    anthropic_api_key_last4: str | None


class AiSettingsOut(BaseModel):
    ai_enabled: bool
    ai_provider: AiProviderKind
    ollama_url: str
    ollama_model: str
    openai_base_url: str
    openai_model: str
    openai_api_key_set: bool
    openai_api_key_last4: str | None
    anthropic_model: str
    anthropic_api_key_set: bool
    anthropic_api_key_last4: str | None


class AiSettingsUpdateRequest(BaseModel):
    ai_enabled: bool | None = None
    ai_provider: AiProviderKind | None = None
    ollama_url: str | None = None
    ollama_model: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_api_key: str | None = None
    clear_openai_api_key: bool = False
    anthropic_model: str | None = None
    anthropic_api_key: str | None = None
    clear_anthropic_api_key: bool = False


class AiStatusOut(BaseModel):
    reachable: bool
    models: list[str]
    error: str | None


class RelocateRequest(BaseModel):
    new_path: str


class ResetRequest(BaseModel):
    confirm: str


class DeleteScopeResult(BaseModel):
    deleted_count: int


class SourceFileSummary(BaseModel):
    """One entry per distinct uploaded PDF that has committed transactions -
    powers Settings' "delete everything from this upload" list. Transactions
    committed before source_filename existed (see migrations.py) have none
    and are simply omitted from this list - there's no file left to name."""

    filename: str
    transaction_count: int


class PathCheckRequest(BaseModel):
    path: str


class PathCheckResult(BaseModel):
    valid: bool
    resolved_path: str
    free_bytes: int | None
    error: str | None


class MetricCards(BaseModel):
    net_expenditure: float
    total_inflow: float
    total_outflow: float


class CashFlowMonth(BaseModel):
    month: str
    inflow: float
    outflow: float


# Same shape as CashFlowMonth by coincidence, not by contract - kept as a
# distinct importable name since the two come from different endpoints
# (per-request-range cash_flow vs. the global /monthly-totals list), but
# there's no reason to maintain two identical field lists.
MonthlyTotal = CashFlowMonth


class CategoryBreakdownSlice(BaseModel):
    category: str
    amount: float
    pct: float


class VelocityPoint(BaseModel):
    day: int
    date: str
    current_period_cumulative: float
    previous_period_cumulative: float


class TopEntry(BaseModel):
    name: str
    amount: float


class DashboardSummaryOut(BaseModel):
    date_from: str
    date_to: str
    metrics: MetricCards
    cash_flow: list[CashFlowMonth]
    category_breakdown: list[CategoryBreakdownSlice]
    spend_velocity: list[VelocityPoint]
    top_merchants: list[TopEntry]
    top_paynow_contacts: list[TopEntry]
