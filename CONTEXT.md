# Domain & Module Glossary

Names settled during architecture review (`/improve-codebase-architecture`, see the report in the OS temp dir).
Some of these modules don't exist as separate files yet — the name is fixed even where the code hasn't caught up,
so later work builds toward the same target instead of re-naming it.

## PendingBatch

The reviewable, commit-or-discard set of rows a statement upload or a Recategorize run stages before anything is
written to `transactions`. **Landed (step 1):** the create/current/get/get_by_id/update_row/delete/reset lifecycle
that used to be implemented twice (`engine/staging_store.py`'s `StagingStore` class+singleton and
`engine/recategorize_job.py`'s module-level globals) now lives once, in `engine/pending_batch.py`'s generic
`PendingBatchStore`. `StagingStore` is a thin subclass fixing `row_key_field="index"`; `recategorize_job.py` keeps
its module-level function API unchanged but delegates to a `PendingBatchStore` instance internally — no router or
API-contract changes were needed. Direct unit tests for the generic store live in `test_pending_batch.py`
(including a test asserting the two-independent-singleton-slots behavior below).

Known wrinkle: today a staging batch and a recategorize batch can be pending *simultaneously* (they're separate
singletons, each only guards against a second batch of its own kind). **Decided: preserve this** — the deepened
module keeps two independent singleton slots rather than unifying to "one pending batch of any kind," to avoid
changing user-facing behavior. (Confirmed still true post-landing: each `PendingBatchStore` instance is fully
independent — see `test_two_stores_are_independent_singleton_slots`.)

**Landed (step 2):** the row-level response/request shape is unified too. `StagingRowOut`/`RecategorizeRowOut`
(previously `index`/`transaction_id`) collapsed into one `BatchRowOut` with a shared `key: int` field, matching
`RuleRerunRowSnapshot`'s own pre-existing `key` convention; `StagingRowUpdateRequest`/`RecategorizeRowUpdateRequest`
collapsed into `BatchRowUpdateRequest`. `routers/statements.py` and `routers/transactions.py` keep their own
`/rules`, `/rules/undo`, `/commit` endpoints and batch-level response types (`StagingBatchOut`/`RecategorizeBatchOut`
etc. still differ — their batch-level metadata genuinely differs: source_filenames/accounts/new_extracted vs.
date_from/date_to/scanned, so forcing one shape there would just trade real duplication for a pile of
kind-conditional nullable fields). That's what makes `BatchActions` (below) viable on the frontend.

## CategorizationRequest / CategorizationRuleset

**Landed.** The deepened interface for `engine/rules.py::categorize()`, replacing its previous 7 loose
positional/keyword parameters (raw_description, rules, contact_identifiers, amount, category_directions,
has_card_account, posting_account_is_card) — split, not combined into one blob, because the two halves have
different lifetimes at every real call site (`routers/statements.py`, `routers/transactions.py`,
`engine/rule_rerun.py` — three callers, not the two the initial report counted). `CategorizationRequest` is per-row
(`raw_description`, `amount`, `posting_account_is_card` — the last one lives here, not on the ruleset, because it
depends on which account the row posted to); `CategorizationRuleset` is built once per upload/recategorize/rerun
pass and passed unchanged to every row in that pass (`rules`, `contact_identifiers`, `category_directions`,
`has_card_account`). `categorize()` itself stays a pure function — no DB access — that's existing depth worth
keeping, unaffected by this change. `engine/rule_rerun.py::rerun_rules_on_batch` keeps its own pre-existing generic
4-parameter signature (unaffected by this refactor, no caller changes needed) and builds one `CategorizationRuleset`
internally before its per-row loop. `test_rules_engine.py` gained a `cat()` test-local builder (mirrors the real
callers' request/ruleset construction) and a `test_one_ruleset_is_safely_reused_across_many_requests` test.

## Rule catalog

**Landed.** Owns rule creation, priority allocation, and direction derivation (a category-assigning rule's direction
always matches its target category's, per `engine/rules.py`'s `_category_direction`). Extracted out of `repo.py`'s
grab bag into its own module, `app/rule_catalog.py` (`fetch_active_rules`, `next_user_rule_priority`,
`category_direction`, `insert_rule`) — a sibling of `repo.py`, not under `engine/`, since it does DB access.
`routers/rules.py`, `routers/statements.py`, `routers/transactions.py` import it directly instead of going through
`repo`. Direct unit tests now live in `test_rule_catalog.py` (previously zero — only reachable through router
integration tests).

## Contact directory

**Landed.** Owns contact creation and PayNow-identifier lookup/replacement. Extracted out of `repo.py`'s grab bag
into `app/contact_directory.py` (`fetch_contact_identifiers`, `find_contact_id_by_identifier`, `insert_contact`,
`replace_contact_identifiers`). `routers/contacts.py`, `routers/statements.py`, `routers/transactions.py` import it
directly instead of going through `repo`. Direct unit tests now live in `test_contact_directory.py`.

`repo.py` itself is no longer a grab bag: it keeps only `categories`-table lookups
(`fetch_category_directions`, `fetch_ai_target_categories`) and `apply_save_as_rule_and_contact`, which stays there
because it's genuinely cross-cutting — one "Save as rule" + "Save as contact mapping" quick action can create both
a rule and a contact in one call, so it can't live wholly inside either new module without that module importing
the other back.

## AI provider configuration

**Landed.** Validates and redacts the Ollama / OpenAI-compatible / Anthropic provider settings. Moved out of the
Settings grab-bag into its own module and router, `app/routers/ai_settings.py`, mounted at its own `/api/ai`
prefix (`GET /api/ai/status`, `PATCH /api/ai`) rather than nested under `/api/settings/*` — the module boundary is
reflected in the route surface, not just the file layout. `redact_ai_settings` (renamed from the old private
`_redact`) is exported for `routers/settings.py`'s overview endpoint to reuse. `frontend/src/api/hooks.ts`'s
`useAiStatus`/`useUpdateAiSettings` call the new prefix.

## Data lifecycle

**Landed (backend + Appearance).** Relocate, Nuclear Reset, and the three scoped deletes (rules/contacts/
transactions) — genuinely one concept (destructive actions on the DB file itself), distinct from AI provider
configuration and Appearance. Moved into its own module and router, `app/routers/data_lifecycle.py`, mounted at
its own `/api/data-lifecycle` prefix (`/relocate`, `/reset`, `/delete-rules`, `/delete-contacts`,
`/delete-transactions`) rather than nested under `/api/settings/*`. It imports `build_settings_out` from
`routers/settings.py` (renamed from the old private `_settings_out`) so `/relocate` can keep returning the same
full settings snapshot the frontend expects. `frontend/src/api/hooks.ts`'s `useRelocateDb`/`useResetDb`/
`useDeleteAll*` call the new prefix.

**Appearance** (accent color) turned out to already be entirely frontend-only — `lib/accentColor.ts` persists to
`localStorage`, no backend endpoint exists for it at all — so it needed no backend module, only extraction out of
`Settings.tsx` into its own component: `AppearanceSection` now lives in `frontend/src/components/AppearanceSection.tsx`.

`routers/settings.py` itself is now just the Settings-page overview: `GET /api/settings` aggregates localization +
the (still-redacted) AI fields + db-file info into one snapshot, via `build_settings_out`. The rest of
`Settings.tsx` (`AiSection`, the Database/Danger-Zone cards and their modals) was left in place — not part of any
locked decision from the grilling loop, so not restructured in this pass.

## BatchActions

**Landed.** The frontend's bundle of apply / createRule / undoRule / commit / discard callbacks plus their pending
flags, which `components/ReviewDialog.tsx` needs from whichever PendingBatch (staging or recategorize) it's
currently showing. `frontend/src/api/hooks.ts`'s `useBatchActions(kind, batchId)` — `kind: 'staging' | 'recategorize'`
— replaced the ten separate staging/recategorize hooks (`useUpdateStagingRow`/`useUpdateRecategorizeRow`,
`useCreateRuleFromStagingBatch`/`useCreateRuleFromRecategorizeBatch`, etc.) with five `kind`-parameterized ones
plus the bundling hook itself; `StagingReviewDialog.tsx`/`RecategorizeReviewDialog.tsx` each now make one
`useBatchActions()` call instead of six individual hook calls plus their own `handleApplyRow`/`handleCreateRule`
wiring. `types.ts`'s row type (`StagingRow`/`RecategorizeRow` → `BatchRow`, matching the backend's `BatchRowOut`)
and undo-request type (`StagingRuleUndoRequest`/`RecategorizeRuleUndoRequest` → `BatchRuleUndoRequest`) were
unified the same way. `useUploadStatement`/`useRecategorizeTransactions`/`useCurrentStagingBatch`/
`useCurrentRecategorizeBatch` stay separate — seeding a batch is still the one place upload and recategorize
genuinely differ. Verified live: upload → apply category → create rule → undo → commit, and
recategorize → apply category → commit, both exercised end-to-end in the browser against a fresh server.
