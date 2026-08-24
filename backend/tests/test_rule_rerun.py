"""Covers the review dialogs' "Create Rule" action (routers/statements.py's
and routers/transactions.py's `.../rules` and `.../rules/undo` endpoints):
creating a rule from a staging/recategorize batch row should retroactively
resolve every other matching, still-unresolved row in the same batch, and
undo should cleanly reverse both the rule and every row it touched."""

import pytest
from fastapi.testclient import TestClient

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


def _force_two_matching_rows(batch):
    """Overwrites two of the batch's already-parsed rows into a known,
    controllable "unresolved outflow" state sharing a merchant keyword no
    default rule matches - so this test doesn't depend on the sanitized
    sample PDF's exact transaction set."""
    target_rows = batch.rows[:2]
    for i, row in enumerate(target_rows):
        row.raw_description = f"POS PURCHASE MEGAMART SG {i}"
        row.amount = -12.5
        row.category = "Others"
        row.subcategory = None
        row.matched_label = None
        row.is_excluded = False
        row.exclusion_reason = None
        row.needs_review = False
        row.contact_id = None
        row.manually_edited = False
        row.is_duplicate = False
    return target_rows


def test_create_rule_from_staging_batch_applies_retroactively(client):
    from app.engine.staging_store import get_store

    batch_id = _upload(client).json()["batch_id"]
    batch = get_store().current()
    target_rows = _force_two_matching_rows(batch)
    target_keys = {r.index for r in target_rows}

    resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["rule_id"] > 0

    updated_keys = {r["key"] for r in result["updated_rows"]}
    assert target_keys <= updated_keys
    for r in result["updated_rows"]:
        if r["key"] in target_keys:
            assert r["category"] == "Others"  # the previous value, for undo

    rows_by_index = {r["key"]: r for r in result["batch"]["rows"]}
    for key in target_keys:
        assert rows_by_index[key]["category"] == "Groceries"
        assert rows_by_index[key]["matched_label"] == "Megamart"

    rules = client.get("/api/rules").json()
    assert any(r["match_pattern"] == "MEGAMART" and r["target_category"] == "Groceries" for r in rules)


def test_create_rule_skips_manually_edited_rows(client):
    from app.engine.staging_store import get_store

    batch_id = _upload(client).json()["batch_id"]
    batch = get_store().current()
    target_rows = _force_two_matching_rows(batch)
    target_rows[1].manually_edited = True  # simulate the user having already resolved this one by hand

    resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    assert resp.status_code == 200
    updated_keys = {r["key"] for r in resp.json()["updated_rows"]}
    assert target_rows[0].index in updated_keys
    assert target_rows[1].index not in updated_keys


def test_create_rule_does_not_regress_unrelated_ai_suggested_rows(client):
    """Reproduces the reported bug: creating a rule that an AI-suggested row
    doesn't even match must not wipe that row's already-applied AI answer -
    see rule_rerun.py's ai_suggested-aware skip."""
    from app.engine.staging_store import get_store

    batch_id = _upload(client).json()["batch_id"]
    batch = get_store().current()
    _force_two_matching_rows(batch)

    # Simulate the background AI job having already resolved a third,
    # unrelated row - same shape apply_ai_suggestions leaves behind:
    # ai_suggested set, category/matched_label overwritten, manually_edited
    # still False (nobody's reviewed it yet).
    ai_row = batch.rows[2]
    ai_row.raw_description = "SOME RANDOM MERCHANT XYZ"
    ai_row.category = "Dining"
    ai_row.matched_label = "Random Merchant"
    ai_row.ai_suggested = True
    ai_row.ai_category = "Dining"
    ai_row.ai_label = "Random Merchant"
    ai_row.manually_edited = False

    resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    assert resp.status_code == 200
    result = resp.json()

    updated_keys = {r["key"] for r in result["updated_rows"]}
    assert ai_row.index not in updated_keys  # untouched by the unrelated rule

    rows_by_index = {r["key"]: r for r in result["batch"]["rows"]}
    assert rows_by_index[ai_row.index]["category"] == "Dining"
    assert rows_by_index[ai_row.index]["matched_label"] == "Random Merchant"
    assert rows_by_index[ai_row.index]["ai_suggested"] is True


def test_create_rule_supersedes_ai_suggested_row_when_new_rule_actually_matches(client):
    """The opposite case: a genuinely matching new rule still outranks an
    unreviewed AI guess, same priority order the rest of the app follows."""
    from app.engine.staging_store import get_store

    batch_id = _upload(client).json()["batch_id"]
    batch = get_store().current()
    ai_row = batch.rows[0]
    ai_row.raw_description = "POS PURCHASE MEGAMART SG 0"
    ai_row.amount = -12.5
    ai_row.category = "Dining"  # AI's (wrong) guess
    ai_row.subcategory = None
    ai_row.matched_label = "Some AI Label"
    ai_row.ai_suggested = True
    ai_row.ai_category = "Dining"
    ai_row.ai_label = "Some AI Label"
    ai_row.manually_edited = False
    ai_row.is_duplicate = False

    resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    assert resp.status_code == 200
    result = resp.json()
    updated_keys = {r["key"] for r in result["updated_rows"]}
    assert ai_row.index in updated_keys  # a genuinely matching new rule still wins

    rows_by_index = {r["key"]: r for r in result["batch"]["rows"]}
    assert rows_by_index[ai_row.index]["category"] == "Groceries"


def test_create_rule_rejects_blank_pattern(client):
    batch_id = _upload(client).json()["batch_id"]
    resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "   ", "target_category": "Groceries"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_RULE_PATTERN"


def test_undo_rule_from_staging_batch_reverts_rows_and_deletes_rule(client):
    from app.engine.staging_store import get_store

    batch_id = _upload(client).json()["batch_id"]
    batch = get_store().current()
    target_rows = _force_two_matching_rows(batch)
    target_keys = {r.index for r in target_rows}

    create_resp = client.post(
        f"/api/statements/staging/{batch_id}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    result = create_resp.json()

    undo_resp = client.post(
        f"/api/statements/staging/{batch_id}/rules/undo",
        json={"rule_id": result["rule_id"], "rows": result["updated_rows"]},
    )
    assert undo_resp.status_code == 200
    rows_by_index = {r["key"]: r for r in undo_resp.json()["rows"]}
    for key in target_keys:
        row_out = rows_by_index[key]
        assert row_out["category"] == "Others"
        assert row_out["matched_label"] is None
        assert row_out["needs_review"] is False

    rules = client.get("/api/rules").json()
    assert not any(r["id"] == result["rule_id"] for r in rules)


def test_create_rule_from_recategorize_batch_applies_retroactively(client):
    from app.engine import recategorize_job

    upload_resp = _upload(client).json()
    client.post(f"/api/statements/staging/{upload_resp['batch_id']}/commit")

    recat_resp = client.post(
        "/api/transactions/recategorize", json={"date_from": "2024-01", "date_to": "2024-12"}
    ).json()
    batch = recategorize_job.current()
    target_rows = batch.rows[:2]
    for i, row in enumerate(target_rows):
        row.raw_description = f"POS PURCHASE MEGAMART SG {i}"
        row.amount = -12.5
        row.category = "Others"
        row.subcategory = None
        row.matched_label = None
        row.is_excluded = False
        row.exclusion_reason = None
        row.needs_review = False
        row.contact_id = None
        row.manually_edited = False
    target_keys = {r.transaction_id for r in target_rows}

    resp = client.post(
        f"/api/transactions/recategorize/{recat_resp['batch_id']}/rules",
        json={"match_pattern": "MEGAMART", "target_category": "Groceries"},
    )
    assert resp.status_code == 200
    result = resp.json()
    updated_keys = {r["key"] for r in result["updated_rows"]}
    assert target_keys <= updated_keys

    rows_by_id = {r["key"]: r for r in result["batch"]["rows"]}
    for key in target_keys:
        assert rows_by_id[key]["category"] == "Groceries"

    undo_resp = client.post(
        f"/api/transactions/recategorize/{recat_resp['batch_id']}/rules/undo",
        json={"rule_id": result["rule_id"], "rows": result["updated_rows"]},
    )
    assert undo_resp.status_code == 200
    rows_by_id = {r["key"]: r for r in undo_resp.json()["rows"]}
    for key in target_keys:
        assert rows_by_id[key]["category"] == "Others"

    rules = client.get("/api/rules").json()
    assert not any(r["id"] == result["rule_id"] for r in rules)
