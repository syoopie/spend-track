import pytest
from fastapi.testclient import TestClient

from app.engine.ai_providers.base import AiProviderUnavailableError, AiSuggestion, ProviderHealth

ACCOUNT_SAMPLE = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _upload(client, path=ACCOUNT_SAMPLE):
    with open(path, "rb") as f:
        return client.post("/api/statements/upload", files={"files": ("statement.pdf", f, "application/pdf")})


def _enable_ai(client):
    resp = client.patch(
        "/api/ai", json={"ai_enabled": True, "ai_provider": "ollama", "ollama_model": "llama3.1"}
    )
    assert resp.status_code == 200, resp.text


class _FakeProvider:
    """Stands in for a real OllamaProvider/etc. - suggests a category for the
    first candidate it's given (if any), so tests don't need to know exactly
    which raw description in the sample PDF lands in the fallback tier."""

    def __init__(self, reachable=True, health_error=None, raise_on_categorize=None, target_category="Shopping"):
        self.reachable = reachable
        self.health_error = health_error
        self.raise_on_categorize = raise_on_categorize
        self.target_category = target_category
        self.categorize_calls = []

    def check_health(self):
        return ProviderHealth(reachable=self.reachable, models=["llama3.1"], error=self.health_error)

    def categorize(self, candidates, categories, *, cancel_key=None):
        self.categorize_calls.append(candidates)
        if self.raise_on_categorize:
            raise self.raise_on_categorize
        if not candidates:
            return []
        first = candidates[0]
        return [
            AiSuggestion(
                index=first.index, category=self.target_category, display_label="AI Label", rule_pattern="AI RULE"
            )
        ]


def _staging_current(client):
    resp = client.get("/api/statements/staging/current")
    assert resp.status_code == 200
    return resp.json()


def test_upload_with_ai_disabled_leaves_rows_untouched(client):
    resp = _upload(client)
    body = resp.json()
    assert body["ai_status"] == "disabled"
    assert body["ai_suggested_count"] == 0
    assert all(not r["ai_suggested"] for r in body["rows"])


def test_upload_with_ai_enabled_and_reachable_suggests_categories(client, monkeypatch):
    _enable_ai(client)
    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    upload_body = _upload(client).json()
    assert upload_body["ai_status"] == "running"
    assert upload_body["ai_model"] == "llama3.1"
    # Set synchronously before the background task is scheduled, so it's
    # already present in this same response - the frontend's running-time
    # indicator anchors to this rather than the moment it happened to poll.
    assert upload_body["ai_started_at"] is not None

    final = _staging_current(client)
    assert final["ai_status"] == "done"
    assert final["ai_suggested_count"] >= 1
    suggested = [r for r in final["rows"] if r["ai_suggested"]]
    assert suggested
    assert suggested[0]["category"] == "Shopping"
    assert suggested[0]["matched_label"] == "AI Label"
    assert suggested[0]["ai_rule_pattern"] == "AI RULE"


def test_cancel_staging_ai_job_while_running(client, monkeypatch):
    """TestClient runs the background task to completion before the upload
    response returns, so there's no genuine mid-flight window here (see
    test_recategorize_discard_calls_ai_cancellation's identical caveat) -
    forces the batch back into "running" afterward to test the cancel
    endpoint's own contract: status flips to "cancelled" (not "failed" - the
    batch is fine, the user just stopped waiting), ai_started_at clears, and
    the cancellation registry is told to interrupt this batch's call."""
    from app.engine.ai_providers import cancellation
    from app.engine.staging_store import get_store

    _enable_ai(client)
    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)
    calls = []
    monkeypatch.setattr(cancellation, "cancel", lambda key: calls.append(key))

    body = _upload(client).json()
    batch = get_store().get(body["batch_id"])
    batch.ai_status = "running"

    resp = client.post(f"/api/statements/staging/{body['batch_id']}/ai/cancel")
    assert resp.status_code == 200
    result = resp.json()
    assert result["ai_status"] == "cancelled"
    assert result["ai_warning"] == "AI categorization was cancelled."
    assert result["ai_started_at"] is None
    assert calls == [body["batch_id"]]


def test_cancel_staging_ai_job_when_not_running_is_noop(client, monkeypatch):
    from app.engine.ai_providers import cancellation

    body = _upload(client).json()
    assert body["ai_status"] == "disabled"
    calls = []
    monkeypatch.setattr(cancellation, "cancel", lambda key: calls.append(key))

    resp = client.post(f"/api/statements/staging/{body['batch_id']}/ai/cancel")
    assert resp.status_code == 200
    assert resp.json()["ai_status"] == "disabled"
    assert calls == []


def test_cancel_staging_ai_job_unknown_batch_404(client):
    resp = client.post("/api/statements/staging/nonexistent-batch-id/ai/cancel")
    assert resp.status_code == 404


def test_cancelled_job_runner_does_not_overwrite_cancelled_status(monkeypatch):
    """The race this guards against: the cancel endpoint has already set
    ai_status="cancelled", but provider.categorize() wasn't actually
    interrupted (best-effort - not every platform honors it) and runs to
    completion anyway. run_ai_job's post-call re-fetch must see the batch is
    no longer "running" and leave "cancelled" alone rather than overwriting
    it with "done"."""
    from app.engine import batch_review
    from app.engine.ai_providers.base import AiCandidate
    from app.engine.staging_store import StagingAccount, StagingBatch, StagingRow, get_store

    row = StagingRow(
        index=0,
        account_number="123",
        transaction_date="2024-01-01",
        raw_description="X",
        matched_label=None,
        amount=-1.0,
        fingerprint="fp",
        category="Others",
        subcategory=None,
        is_excluded=False,
        exclusion_reason=None,
        contact_id=None,
        needs_review=False,
        is_duplicate=False,
        original_category="Others",
        original_label=None,
    )
    batch = StagingBatch(
        source_filenames=["f.pdf"],
        bank_name="UOB",
        accounts=[StagingAccount("UOB", "123", "***123", "Savings", is_new=False)],
        rows=[row],
    )
    store = get_store()
    store.reset()
    store.create(batch)
    batch.ai_status = "cancelled"
    batch.ai_warning = "AI categorization was cancelled."

    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)
    candidate = [AiCandidate(index=0, raw_description="X", amount=-1.0, direction="outflow")]
    batch_review.run_ai_job(
        store, batch.batch_id, candidate, [("Shopping", "outflow")], {"ai_provider": "ollama"}, "fallback"
    )

    assert batch.ai_status == "cancelled"
    assert not row.ai_suggested
    store.reset()


def test_upload_with_ai_enabled_and_unreachable_sets_warning(client, monkeypatch):
    _enable_ai(client)
    fake = _FakeProvider(reachable=False, health_error="connection refused")
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    _upload(client)
    final = _staging_current(client)
    assert final["ai_status"] == "failed"
    assert "connection refused" in final["ai_warning"]
    assert final["ai_suggested_count"] == 0


def test_upload_with_ai_categorize_error_sets_warning(client, monkeypatch):
    _enable_ai(client)
    fake = _FakeProvider(reachable=True, raise_on_categorize=AiProviderUnavailableError("timed out"))
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    _upload(client)
    final = _staging_current(client)
    assert final["ai_status"] == "failed"
    assert "timed out" in final["ai_warning"]


def test_background_ai_task_no_op_after_batch_discarded(client, monkeypatch):
    """If the batch is discarded/committed before the background task's
    lookups run, it must exit quietly rather than crash or resurrect a
    deleted batch."""
    from app.engine import batch_review
    from app.engine.ai_providers.base import AiCandidate
    from app.engine.staging_store import get_store

    fake = _FakeProvider(reachable=True)
    candidate = [AiCandidate(index=0, raw_description="X", amount=-1.0, direction="outflow")]
    # No batch was ever created with this id - simulates "already gone".
    batch_review.run_ai_job(
        get_store(),
        "nonexistent-batch-id",
        candidate,
        [("Shopping", "outflow")],
        {"ai_provider": "ollama"},
        "fallback",
    )


def test_patch_staging_row_accepts_rule_pattern(client, monkeypatch):
    _enable_ai(client)
    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)
    _upload(client)
    final = _staging_current(client)
    suggested = next(r for r in final["rows"] if r["ai_suggested"])

    resp = client.patch(
        f"/api/statements/staging/{final['batch_id']}/rows/{suggested['key']}",
        json={
            "category": suggested["category"],
            "save_as_rule": True,
            "rule_pattern": suggested["ai_rule_pattern"],
        },
    )
    assert resp.status_code == 200

    rules = client.get("/api/rules").json()
    assert any(r["match_pattern"] == "AI RULE" for r in rules)


def test_staging_manual_edit_then_restore_default_prefers_ai_suggestion(client, monkeypatch):
    _enable_ai(client)
    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)
    _upload(client)
    final = _staging_current(client)
    suggested = next(r for r in final["rows"] if r["ai_suggested"])
    fallback = "Other Income" if suggested["amount"] > 0 else "Others"

    edited = client.patch(
        f"/api/statements/staging/{final['batch_id']}/rows/{suggested['key']}",
        json={"category": fallback, "matched_label": None},
    ).json()
    edited_row = next(r for r in edited["rows"] if r["key"] == suggested["key"])
    assert edited_row["category"] == fallback
    assert edited_row["matched_label"] is None
    # a manual edit doesn't erase the AI's proposal - it stays available to restore
    assert edited_row["ai_suggested"] is True
    assert edited_row["ai_category"] == "Shopping"

    restored = client.patch(
        f"/api/statements/staging/{final['batch_id']}/rows/{suggested['key']}",
        json={"category": fallback, "restore_default": True},
    ).json()
    restored_row = next(r for r in restored["rows"] if r["key"] == suggested["key"])
    assert restored_row["category"] == "Shopping"
    assert restored_row["matched_label"] == "AI Label"


def test_staging_restore_default_without_ai_suggestion_falls_back_to_original(client):
    _upload(client)
    final = _staging_current(client)
    row = final["rows"][0]
    original_category = row["category"]
    original_label = row["matched_label"]

    client.patch(
        f"/api/statements/staging/{final['batch_id']}/rows/{row['key']}",
        json={"category": "Shopping", "matched_label": "Edited Label"},
    )
    resp = client.patch(
        f"/api/statements/staging/{final['batch_id']}/rows/{row['key']}",
        json={"category": "Shopping", "restore_default": True},
    )
    assert resp.status_code == 200
    restored_row = next(r for r in resp.json()["rows"] if r["key"] == row["key"])
    assert restored_row["category"] == original_category
    assert restored_row["matched_label"] == original_label


# --- recategorize --------------------------------------------------------------


def _upload_and_commit(client, path=ACCOUNT_SAMPLE):
    body = _upload(client, path).json()
    client.post(f"/api/statements/staging/{body['batch_id']}/commit")
    return body


def test_recategorize_with_ai_disabled_reports_disabled(client):
    _upload_and_commit(client)
    resp = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"})
    body = resp.json()
    assert body["ai_status"] == "disabled"
    assert body["ai_suggested_count"] == 0
    assert len(body["rows"]) == body["scanned"]


def test_recategorize_with_ai_enabled_categorizes_leftovers(client, monkeypatch):
    _upload_and_commit(client)
    _enable_ai(client)
    fake = _FakeProvider(reachable=True, target_category="Shopping")
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    resp = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"})
    body = resp.json()
    assert body["ai_status"] == "running"

    current = client.get("/api/transactions/recategorize/current").json()
    assert current["ai_status"] == "done"
    assert current["ai_suggested_count"] >= 1
    suggested_row = next(r for r in current["rows"] if r["ai_suggested"])
    assert suggested_row["category"] == "Shopping"
    assert suggested_row["matched_label"] == "AI Label"
    assert suggested_row["ai_rule_pattern"] == "AI RULE"

    # not written to the DB yet - only committing the batch applies it
    txs_before = client.get("/api/transactions").json()
    assert not any(t["matched_label"] == "AI Label" for t in txs_before)

    client.post(f"/api/transactions/recategorize/{body['batch_id']}/commit")
    txs_after = client.get("/api/transactions").json()
    assert any(t["matched_label"] == "AI Label" and t["category"] == "Shopping" for t in txs_after)


def test_recategorize_current_404_before_any_run(client):
    resp = client.get("/api/transactions/recategorize/current")
    assert resp.status_code == 404


def test_cancel_recategorize_ai_job_while_running(client, monkeypatch):
    """See test_cancel_staging_ai_job_while_running's identical caveat and
    contract - mirrored for the recategorize batch's own AI pass."""
    from app.engine import recategorize_job
    from app.engine.ai_providers import cancellation

    _upload_and_commit(client)
    _enable_ai(client)
    fake = _FakeProvider(reachable=True)
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)
    calls = []
    monkeypatch.setattr(cancellation, "cancel", lambda key: calls.append(key))

    body = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    batch = recategorize_job.get_by_id(body["batch_id"])
    batch.ai_status = "running"

    resp = client.post(f"/api/transactions/recategorize/{body['batch_id']}/ai/cancel")
    assert resp.status_code == 200
    result = resp.json()
    assert result["ai_status"] == "cancelled"
    assert result["ai_warning"] == "AI categorization was cancelled."
    assert result["ai_started_at"] is None
    assert calls == [body["batch_id"]]


def test_cancel_recategorize_ai_job_unknown_batch_404(client):
    resp = client.post("/api/transactions/recategorize/nonexistent-batch-id/ai/cancel")
    assert resp.status_code == 404


def test_recategorize_row_edit_syncs_into_current_batch(client, monkeypatch):
    _upload_and_commit(client)
    _enable_ai(client)
    fake = _FakeProvider(reachable=True, target_category="Shopping")
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    current = client.get("/api/transactions/recategorize/current").json()
    suggested_row = next(r for r in current["rows"] if r["ai_suggested"])

    resp = client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{suggested_row['key']}",
        json={"category": "Transport", "save_as_rule": True, "rule_pattern": "MANUAL PATTERN"},
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["key"] == suggested_row["key"])
    assert updated_row["category"] == "Transport"
    # the AI's original suggestion is a permanent record - it survives a
    # manual override so the suggestion can still be restored later, even
    # though the row is no longer *currently* showing it
    assert updated_row["ai_suggested"] is True
    assert updated_row["ai_category"] == "Shopping"

    rules = client.get("/api/rules").json()
    assert any(r["match_pattern"] == "MANUAL PATTERN" for r in rules)


def test_recategorize_manual_edit_over_ai_suggestion_keeps_ai_record(client, monkeypatch):
    _upload_and_commit(client)
    _enable_ai(client)
    fake = _FakeProvider(reachable=True, target_category="Shopping")
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    current = client.get("/api/transactions/recategorize/current").json()
    suggested_row = next(r for r in current["rows"] if r["ai_suggested"])
    fallback = "Other Income" if suggested_row["amount"] > 0 else "Others"

    resp = client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{suggested_row['key']}",
        json={"category": fallback, "matched_label": None},
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["key"] == suggested_row["key"])
    assert updated_row["category"] == fallback
    assert updated_row["matched_label"] is None
    # a manual edit is not an unrecoverable delete - the suggestion is
    # retained so it can be restored (see the restore test below)
    assert updated_row["ai_suggested"] is True
    assert updated_row["ai_category"] == "Shopping"
    assert updated_row["ai_label"] == "AI Label"


def test_recategorize_restore_default_after_manual_edit_prefers_ai_suggestion(client, monkeypatch):
    _upload_and_commit(client)
    _enable_ai(client)
    fake = _FakeProvider(reachable=True, target_category="Shopping")
    monkeypatch.setattr("app.engine.ai_providers.build_provider", lambda settings: fake)

    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    current = client.get("/api/transactions/recategorize/current").json()
    suggested_row = next(r for r in current["rows"] if r["ai_suggested"])
    fallback = "Other Income" if suggested_row["amount"] > 0 else "Others"

    client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{suggested_row['key']}",
        json={"category": fallback, "matched_label": None},
    )
    resp = client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{suggested_row['key']}",
        json={"category": fallback, "restore_default": True},
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["key"] == suggested_row["key"])
    assert updated_row["category"] == "Shopping"
    assert updated_row["matched_label"] == "AI Label"
    assert updated_row["ai_suggested"] is True


def test_recategorize_restore_default_without_ai_suggestion_falls_back_to_original(client):
    _upload_and_commit(client)
    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    row = batch["rows"][0]
    original_category = row["category"]
    original_label = row["matched_label"]

    client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{row['key']}",
        json={"category": "Shopping", "matched_label": "Edited Label"},
    )
    resp = client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{row['key']}",
        json={"category": "Shopping", "restore_default": True},
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["key"] == row["key"])
    assert updated_row["category"] == original_category
    assert updated_row["matched_label"] == original_label


def test_recategorize_discard_calls_ai_cancellation(client, monkeypatch):
    """TestClient runs background tasks to completion before client.post(...)
    returns (see conftest/other tests' comments on this), so a genuinely
    still-in-flight call can't be reproduced here - what this verifies is
    the router's contract: discarding always tells the cancellation
    registry about this batch's id, which is what actually interrupts a
    real long-running call against a real server (best-effort, see
    ai_providers/cancellation.py)."""
    from app.engine.ai_providers import cancellation

    _upload_and_commit(client)
    calls = []
    monkeypatch.setattr(cancellation, "cancel", lambda key: calls.append(key))

    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    assert client.delete(f"/api/transactions/recategorize/{batch['batch_id']}").status_code == 204
    assert calls == [batch["batch_id"]]


def test_recategorize_commit_also_cancels_ai(client, monkeypatch):
    from app.engine.ai_providers import cancellation

    _upload_and_commit(client)
    calls = []
    monkeypatch.setattr(cancellation, "cancel", lambda key: calls.append(key))

    batch = client.post("/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}).json()
    assert client.post(f"/api/transactions/recategorize/{batch['batch_id']}/commit").status_code == 200
    assert calls == [batch["batch_id"]]


# --- background AI job must not clobber a row the user already resolved -------


def test_staging_apply_ai_suggestions_skips_manually_edited_rows():
    """If the user resolves a row (via update_staging_row, which sets
    manually_edited=True) before the AI's suggestion for that same row
    comes back, the background job must not silently overwrite their
    choice - see engine/batch_review.py::apply_ai_suggestions."""
    from app.engine import batch_review
    from app.engine.ai_providers.base import AiSuggestion
    from app.engine.staging_store import StagingBatch, StagingRow, get_store

    edited_row = StagingRow(
        index=0, account_number="acc", transaction_date="2024-01-01", raw_description="X", matched_label=None,
        amount=-5.0, fingerprint="fp0", category="Others", subcategory=None, is_excluded=False,
        exclusion_reason=None, contact_id=None, needs_review=False, is_duplicate=False,
        original_category="Others", original_label=None, manually_edited=True,
    )
    untouched_row = StagingRow(
        index=1, account_number="acc", transaction_date="2024-01-01", raw_description="Y", matched_label=None,
        amount=-5.0, fingerprint="fp1", category="Others", subcategory=None, is_excluded=False,
        exclusion_reason=None, contact_id=None, needs_review=False, is_duplicate=False,
        original_category="Others", original_label=None,
    )
    batch = StagingBatch(source_filenames=["f.pdf"], bank_name="UOB", accounts=[], rows=[edited_row, untouched_row])
    suggestions = [
        AiSuggestion(index=0, category="Shopping", display_label="Should not apply", rule_pattern=None),
        AiSuggestion(index=1, category="Shopping", display_label="Should apply", rule_pattern=None),
    ]

    batch_review.apply_ai_suggestions(get_store(), batch, suggestions)

    assert edited_row.category == "Others"  # untouched - the manual edit wins
    assert edited_row.ai_suggested is False
    assert untouched_row.category == "Shopping"
    assert untouched_row.matched_label == "Should apply"
    assert untouched_row.ai_suggested is True


def test_recategorize_apply_ai_suggestions_skips_manually_edited_rows():
    from app.engine import batch_review
    from app.engine.ai_providers.base import AiSuggestion
    from app.engine.recategorize_job import RecategorizeBatch, RecategorizeRow, get_store

    edited_row = RecategorizeRow(
        transaction_id=1, account_number_masked="***1234", transaction_date="2024-01-01", raw_description="X",
        matched_label=None, amount=-5.0, category="Others", subcategory=None, contact_id=None, is_excluded=False,
        exclusion_reason=None, needs_review=False,
        original_category="Others", original_label=None, manually_edited=True,
    )
    untouched_row = RecategorizeRow(
        transaction_id=2, account_number_masked="***1234", transaction_date="2024-01-01", raw_description="Y",
        matched_label=None, amount=-5.0, category="Others", subcategory=None, contact_id=None, is_excluded=False,
        exclusion_reason=None, needs_review=False,
        original_category="Others", original_label=None,
    )
    batch = RecategorizeBatch(
        date_from="2024-01", date_to="2024-01", account_id=None, scanned=2, changed=0,
        rows=[edited_row, untouched_row],
    )
    suggestions = [
        AiSuggestion(index=1, category="Shopping", display_label="Should not apply", rule_pattern=None),
        AiSuggestion(index=2, category="Shopping", display_label="Should apply", rule_pattern=None),
    ]

    batch_review.apply_ai_suggestions(get_store(), batch, suggestions)

    assert edited_row.category == "Others"
    assert edited_row.ai_suggested is False
    assert untouched_row.category == "Shopping"
    assert untouched_row.ai_suggested is True


# --- ai_provider is now a validated enum, not a free string --------------------


def test_update_ai_settings_rejects_unknown_provider(client):
    resp = client.patch("/api/ai", json={"ai_provider": "not-a-real-provider"})
    assert resp.status_code == 422
