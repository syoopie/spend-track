import io

import pytest
from fastapi.testclient import TestClient

ACCOUNT_SAMPLE = "../PDF Examples/UOB/Account Statements/eStatement_29072.23852206947.pdf"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _upload_and_commit(client, path=ACCOUNT_SAMPLE):
    with open(path, "rb") as f:
        resp = client.post(
            "/api/statements/upload", files={"files": ("statement.pdf", f, "application/pdf")}
        )
    body = resp.json()
    client.post(f"/api/statements/staging/{body['batch_id']}/commit")
    return body


# --- categories -------------------------------------------------------


def test_categories_seeded_with_defaults(client):
    resp = client.get("/api/categories")
    cats = resp.json()
    names = [c["name"] for c in cats]
    assert names == [
        "Sports & Hobbies", "Beauty", "Food & Drink", "Shopping", "Transport", "Home", "Bills & Fees",
        "Entertainment", "Healthcare", "Education", "Groceries", "Investing", "Paynow",
        "Salary", "Refunds & Reimbursements", "Investment Income", "Paynow Received",
    ]
    by_name = {c["name"]: c for c in cats}
    assert by_name["Transport"]["direction"] == "outflow"
    assert by_name["Salary"]["direction"] == "inflow"
    assert by_name["Refunds & Reimbursements"]["direction"] == "inflow"


def test_categories_hidden_others_excluded_unless_requested(client):
    resp = client.get("/api/categories")
    assert "Others" not in [c["name"] for c in resp.json()]

    resp_all = client.get("/api/categories", params={"include_hidden": True})
    names = [c["name"] for c in resp_all.json()]
    assert "Others" in names
    assert "Other Income" in names
    assert len(names) == 19


def test_create_category(client):
    resp = client.post("/api/categories", json={"name": "Travel", "hue": 100})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Travel"


# --- accounts + transactions -------------------------------------------


def test_accounts_and_transactions_after_commit(client):
    _upload_and_commit(client)

    accounts = client.get("/api/accounts").json()
    assert len(accounts) == 1
    assert accounts[0]["bank_name"] == "UOB"

    txs = client.get("/api/transactions").json()
    assert len(txs) == 39
    assert all(t["account_id"] == accounts[0]["id"] for t in txs)


def test_transactions_month_filter(client):
    _upload_and_commit(client)
    txs = client.get("/api/transactions", params={"date_from": "2026-05", "date_to": "2026-05"}).json()
    assert len(txs) == 39
    txs_other = client.get("/api/transactions", params={"date_from": "2026-06", "date_to": "2026-06"}).json()
    assert txs_other == []


def test_transactions_excludes_excluded_by_default(client):
    _upload_and_commit(client)
    # exclude one transaction manually via a rule would be the real flow;
    # here we just check the include_excluded flag round-trips correctly
    # with no excluded rows present.
    txs = client.get("/api/transactions", params={"include_excluded": True}).json()
    assert len(txs) == 39


def test_refund_pairing_404_when_none_exists(client):
    _upload_and_commit(client)
    txs = client.get("/api/transactions").json()
    resp = client.get(f"/api/transactions/{txs[0]['id']}/refund-pairing")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NO_REFUND_PAIRING"


def test_update_committed_transaction_category_and_label(client):
    _upload_and_commit(client)
    tx = client.get("/api/transactions").json()[0]

    updated = client.patch(
        f"/api/transactions/{tx['id']}",
        json={"category": "Groceries", "matched_label": "Corrected Name"},
    ).json()
    assert updated["category"] == "Groceries"
    assert updated["matched_label"] == "Corrected Name"
    # untouched fields survive the partial update
    assert updated["raw_description"] == tx["raw_description"]
    assert updated["amount"] == tx["amount"]


def test_excluding_a_transaction_via_patch_hides_it_by_default(client):
    _upload_and_commit(client)
    tx = client.get("/api/transactions").json()[0]

    excluded = client.patch(
        f"/api/transactions/{tx['id']}",
        json={"is_excluded": True, "exclusion_reason": "Self-transfer"},
    ).json()
    assert excluded["is_excluded"] is True
    assert excluded["exclusion_reason"] == "Self-transfer"
    assert all(t["id"] != tx["id"] for t in client.get("/api/transactions").json())

    unexcluded = client.patch(f"/api/transactions/{tx['id']}", json={"is_excluded": False}).json()
    assert unexcluded["is_excluded"] is False
    assert unexcluded["exclusion_reason"] is None  # stale reason cleared
    assert any(t["id"] == tx["id"] for t in client.get("/api/transactions").json())


def test_update_missing_transaction_404s(client):
    resp = client.patch("/api/transactions/999999", json={"category": "Groceries"})
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "TRANSACTION_NOT_FOUND"


def test_recategorize_stages_a_batch_and_only_writes_on_commit(client):
    """Recategorize is treated the same as an upload: the POST proposes
    results into a pending, reviewable batch - it must not touch the DB
    until that batch is explicitly committed."""
    _upload_and_commit(client)
    tx = client.get("/api/transactions").json()[0]
    client.patch(
        f"/api/transactions/{tx['id']}",
        json={"category": "Groceries", "matched_label": "Manual Override"},
    )

    def _fetch(tx_id):
        rows = client.get("/api/transactions", params={"include_excluded": True}).json()
        return next(t for t in rows if t["id"] == tx_id)

    # out of range: an empty batch is still staged (not applied) - discard it
    # to free the "only one pending batch" slot for the real run below.
    resp_out = client.post("/api/transactions/recategorize", json={"date_from": "2026-06", "date_to": "2026-06"})
    assert resp_out.status_code == 200
    out_body = resp_out.json()
    assert out_body["scanned"] == 0
    assert out_body["rows"] == []
    assert client.delete(f"/api/transactions/recategorize/{out_body['batch_id']}").status_code == 204
    assert _fetch(tx["id"])["category"] == "Groceries"

    # in range: proposes the recomputed result but does not apply it yet
    resp = client.post("/api/transactions/recategorize", json={"date_from": "2026-05", "date_to": "2026-05"})
    body = resp.json()
    assert body["scanned"] == 39
    assert body["changed"] >= 1
    assert len(body["rows"]) == 39
    assert _fetch(tx["id"])["category"] == "Groceries"  # still untouched - only proposed so far

    # a second run is rejected while this one is still pending
    conflict = client.post("/api/transactions/recategorize", json={"date_from": "2026-05", "date_to": "2026-05"})
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "RECATEGORIZE_BATCH_EXISTS"

    # committing applies every proposed row to the DB
    commit_resp = client.post(f"/api/transactions/recategorize/{body['batch_id']}/commit")
    assert commit_resp.status_code == 200
    assert commit_resp.json()["transactions_committed"] == 39
    reverted = _fetch(tx["id"])
    assert (reverted["category"], reverted["matched_label"]) != ("Groceries", "Manual Override")

    # the batch is gone once committed, freeing the slot for a future run
    assert client.get("/api/transactions/recategorize/current").status_code == 404


def test_recategorize_discard_leaves_db_untouched(client):
    _upload_and_commit(client)
    tx = client.get("/api/transactions").json()[0]

    body = client.post("/api/transactions/recategorize", json={"date_from": "2026-05", "date_to": "2026-05"}).json()
    assert client.delete(f"/api/transactions/recategorize/{body['batch_id']}").status_code == 204
    assert client.get("/api/transactions/recategorize/current").status_code == 404

    refetched = next(t for t in client.get("/api/transactions").json() if t["id"] == tx["id"])
    assert refetched["category"] == tx["category"]
    assert refetched["matched_label"] == tx["matched_label"]


def test_recategorize_row_edit_is_staged_until_commit(client):
    _upload_and_commit(client)
    batch = client.post("/api/transactions/recategorize", json={"date_from": "2026-05", "date_to": "2026-05"}).json()
    row = batch["rows"][0]

    resp = client.patch(
        f"/api/transactions/recategorize/{batch['batch_id']}/rows/{row['transaction_id']}",
        json={"category": "Entertainment", "save_as_rule": True, "rule_pattern": "MANUAL RULE PATTERN"},
    )
    assert resp.status_code == 200
    updated_row = next(r for r in resp.json()["rows"] if r["transaction_id"] == row["transaction_id"])
    assert updated_row["category"] == "Entertainment"

    # not written to the DB yet
    still_unwritten = next(t for t in client.get("/api/transactions").json() if t["id"] == row["transaction_id"])
    assert still_unwritten["category"] != "Entertainment"

    # the rule itself, though, is created immediately (independent of commit)
    rules = client.get("/api/rules").json()
    assert any(r["match_pattern"] == "MANUAL RULE PATTERN" for r in rules)

    # committing writes the edited value
    client.post(f"/api/transactions/recategorize/{batch['batch_id']}/commit")
    written = next(t for t in client.get("/api/transactions").json() if t["id"] == row["transaction_id"])
    assert written["category"] == "Entertainment"


# --- contacts -----------------------------------------------------------


def test_create_list_update_delete_contact(client):
    created = client.post(
        "/api/contacts",
        json={
            "name": "Auntie Mei",
            "default_category": "Paynow",
            "identifiers": ["+65 9123 4567"],
        },
    ).json()
    assert created["identifiers"] == ["+65 9123 4567"]
    assert created["historical_spend"] == 0

    listed = client.get("/api/contacts").json()
    assert any(c["name"] == "Auntie Mei" for c in listed)

    updated = client.patch(
        f"/api/contacts/{created['id']}", json={"identifiers": ["+65 9123 4567", "UEN12345678A"]}
    ).json()
    assert set(updated["identifiers"]) == {"+65 9123 4567", "UEN12345678A"}

    resp = client.delete(f"/api/contacts/{created['id']}")
    assert resp.status_code == 204
    listed_after = client.get("/api/contacts").json()
    assert all(c["id"] != created["id"] for c in listed_after)


def test_import_contacts_csv(client):
    csv_content = "Name,Identifier,Category\nBoon Heng,BOON HENG PTE,Paynow\nMum,+65 9345 1234,Paynow\n"
    resp = client.post(
        "/api/contacts/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    assert resp.json() == {"contacts_created": 2, "contacts_updated": 0}

    contacts = client.get("/api/contacts").json()
    names = {c["name"] for c in contacts}
    assert {"Boon Heng", "Mum"} <= names


def test_import_contacts_csv_skips_already_mapped_identifier(client):
    csv_content = "Name,Identifier,Category\nBoon Heng,BOON HENG PTE,Paynow\n"
    client.post(
        "/api/contacts/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    resp = client.post(
        "/api/contacts/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.json() == {"contacts_created": 0, "contacts_updated": 0}


# --- rules ----------------------------------------------------------------


def test_create_list_reorder_delete_rules(client):
    r1 = client.post("/api/rules", json={"match_pattern": "SP GROUP", "target_category": "Bills & Fees"}).json()
    r2 = client.post("/api/rules", json={"match_pattern": "GRAB", "target_category": "Transport"}).json()
    assert r1["priority"] == 1
    assert r2["priority"] == 2
    assert r1["is_default"] is False

    reordered = client.post("/api/rules/reorder", json={"ordered_ids": [r2["id"], r1["id"]]}).json()
    assert reordered[0]["id"] == r2["id"]
    assert reordered[0]["priority"] == 1

    resp = client.delete(f"/api/rules/{r1['id']}")
    assert resp.status_code == 204
    remaining = client.get("/api/rules").json()
    assert len(remaining) == 1


def test_reorder_rejects_a_partial_or_unknown_id_list(client):
    r1 = client.post("/api/rules", json={"match_pattern": "SP GROUP", "target_category": "Bills & Fees"}).json()
    r2 = client.post("/api/rules", json={"match_pattern": "GRAB", "target_category": "Transport"}).json()

    # partial: omits r2 entirely, which would otherwise keep its old
    # priority and could collide with the freshly-assigned 1..N block
    resp = client.post("/api/rules/reorder", json={"ordered_ids": [r1["id"]]})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "REORDER_ID_MISMATCH"

    # unknown id mixed in with a real one
    resp = client.post("/api/rules/reorder", json={"ordered_ids": [r1["id"], r2["id"], 999999]})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "REORDER_ID_MISMATCH"


def test_default_rules_hidden_and_immutable(client):
    visible = client.get("/api/rules").json()
    assert all(not r["is_default"] for r in visible)

    with_defaults = client.get("/api/rules", params={"include_default": True}).json()
    default_rules = [r for r in with_defaults if r["is_default"]]
    assert len(default_rules) > 50
    sample = default_rules[0]

    assert client.patch(f"/api/rules/{sample['id']}", json={"priority": 1}).status_code == 403
    assert client.delete(f"/api/rules/{sample['id']}").status_code == 403
    reorder_resp = client.post("/api/rules/reorder", json={"ordered_ids": [sample["id"]]})
    assert reorder_resp.status_code == 403


def test_exclusion_rule_create_and_update(client):
    r = client.post(
        "/api/rules",
        json={
            "match_pattern": "INTERNAL TRANSFER",
            "is_exclusion_rule": True,
            "exclusion_reason": "Self-transfer",
        },
    ).json()
    assert r["is_exclusion_rule"] is True
    updated = client.patch(f"/api/rules/{r['id']}", json={"exclusion_reason": "Updated reason"}).json()
    assert updated["exclusion_reason"] == "Updated reason"


# --- settings ---------------------------------------------------------------


def test_get_settings_reports_path_and_size(client):
    _upload_and_commit(client)
    resp = client.get("/api/settings").json()
    assert resp["schema_version"] == 5
    assert resp["size_bytes"] > 0
    assert resp["country_code"] == "SG"
    assert resp["currency_code"] == "SGD"
    assert resp["currency_symbol"] == "$"
    assert resp["transfer_scheme_name"] == "PayNow"
    assert "UOB" in resp["supported_banks"]


def test_reset_requires_delete_confirmation(client):
    _upload_and_commit(client)
    resp = client.post("/api/settings/reset", json={"confirm": "nope"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "RESET_CONFIRMATION_MISMATCH"


def test_reset_wipes_data_and_reinitializes_schema(client):
    _upload_and_commit(client)
    assert len(client.get("/api/transactions", params={"include_excluded": True}).json()) == 39

    resp = client.post("/api/settings/reset", json={"confirm": "DELETE"})
    assert resp.status_code == 204

    assert client.get("/api/transactions").json() == []
    assert client.get("/api/accounts").json() == []
    cats = client.get("/api/categories").json()
    assert len(cats) == 17  # default categories re-seeded (Others/Other Income are hidden)


def test_delete_rules_requires_confirmation_and_only_removes_user_rules(client):
    client.post("/api/rules", json={"match_pattern": "SP GROUP", "target_category": "Bills & Fees"})
    default_count_before = len(client.get("/api/rules", params={"include_default": True}).json())

    resp = client.post("/api/settings/delete-rules", json={"confirm": "nope"})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "RESET_CONFIRMATION_MISMATCH"

    resp = client.post("/api/settings/delete-rules", json={"confirm": "DELETE"})
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 1

    assert client.get("/api/rules").json() == []
    # default rules (is_default=1) must survive - only the user-created one was deleted
    remaining = client.get("/api/rules", params={"include_default": True}).json()
    assert len(remaining) == default_count_before - 1


def test_delete_contacts_removes_all_contacts_and_identifiers(client):
    client.post(
        "/api/contacts",
        json={"name": "Auntie Mei", "default_category": "Paynow", "identifiers": ["+65 9123 4567"]},
    )
    resp = client.post("/api/settings/delete-contacts", json={"confirm": "DELETE"})
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 1
    assert client.get("/api/contacts").json() == []


def test_delete_contacts_nulls_out_contact_id_on_linked_transactions(client):
    """schema.sql declares transactions.contact_id ON DELETE SET NULL, but no
    existing test actually links a transaction to a contact before deleting
    it - this exercises that path end to end rather than just trusting the
    schema declaration."""
    _upload_and_commit(client)
    tx_id = client.get("/api/transactions").json()[0]["id"]
    contact = client.post(
        "/api/contacts",
        json={"name": "Auntie Mei", "default_category": "Paynow", "identifiers": ["+65 9123 4567"]},
    ).json()
    client.patch(f"/api/transactions/{tx_id}", json={"contact_id": contact["id"]})
    linked = next(t for t in client.get("/api/transactions").json() if t["id"] == tx_id)
    assert linked["contact_id"] == contact["id"]

    resp = client.post("/api/settings/delete-contacts", json={"confirm": "DELETE"})
    assert resp.status_code == 200

    survivor = next(t for t in client.get("/api/transactions").json() if t["id"] == tx_id)
    assert survivor["contact_id"] is None  # SET NULL, not left dangling and not an FK error


def test_delete_transactions_clears_transactions_but_keeps_accounts(client):
    _upload_and_commit(client)
    resp = client.post("/api/settings/delete-transactions", json={"confirm": "DELETE"})
    assert resp.status_code == 200
    assert resp.json()["deleted_count"] == 39
    assert client.get("/api/transactions").json() == []
    assert len(client.get("/api/accounts").json()) == 1  # account itself is untouched


def test_relocate_moves_db_file_and_updates_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_HOME", str(tmp_path / "home"))
    from app.main import app

    with TestClient(app) as client:
        _upload_and_commit(client)
        old_settings = client.get("/api/settings").json()

        new_dir = tmp_path / "relocated"
        new_dir.mkdir()
        new_path = str(new_dir / "moved.db")

        resp = client.post("/api/settings/relocate", json={"new_path": new_path})
        assert resp.status_code == 200
        assert resp.json()["db_path"] == new_path

        from pathlib import Path

        assert Path(new_path).exists()
        assert not Path(old_settings["db_path"]).exists()

        # data survives the move
        txs = client.get("/api/transactions").json()
        assert len(txs) == 39


def test_relocate_to_the_same_path_is_rejected(client):
    _upload_and_commit(client)
    current_path = client.get("/api/settings").json()["db_path"]
    resp = client.post("/api/settings/relocate", json={"new_path": current_path})
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "RELOCATE_SAME_PATH"


# --- dashboard ---------------------------------------------------------------


def test_dashboard_summary_metrics_match_manual_totals(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    assert resp["date_from"] == "2026-05"
    assert resp["date_to"] == "2026-05"

    txs = client.get("/api/transactions").json()
    expected_inflow = round(sum(t["amount"] for t in txs if t["amount"] > 0), 2)
    expected_outflow = round(sum(-t["amount"] for t in txs if t["amount"] < 0), 2)

    assert resp["metrics"]["total_inflow"] == expected_inflow
    assert resp["metrics"]["total_outflow"] == expected_outflow
    assert resp["metrics"]["net_expenditure"] == round(expected_inflow - expected_outflow, 2)


def test_dashboard_defaults_to_single_latest_month(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    assert len(resp["cash_flow"]) == 1
    assert resp["cash_flow"][-1]["month"] == "2026-05"
    assert len(resp["spend_velocity"]) > 0  # single month - velocity is meaningful


def test_dashboard_summary_spans_a_custom_month_range(client):
    _upload_and_commit(client)
    resp = client.get(
        "/api/dashboard/summary", params={"date_from": "2026-03", "date_to": "2026-05"}
    ).json()
    assert resp["date_from"] == "2026-03"
    assert resp["date_to"] == "2026-05"
    assert [c["month"] for c in resp["cash_flow"]] == ["2026-03", "2026-04", "2026-05"]
    # velocity is meaningful for multi-month ranges too - compares the whole
    # selected range's cumulative pace against the immediately preceding
    # same-length range (2025-12 to 2026-02 here)
    assert len(resp["spend_velocity"]) > 0
    assert resp["spend_velocity"][0]["date"] == "2026-03-01"
    # all 39 transactions fall in May, so the wider range's totals still match May alone
    assert resp["metrics"]["total_outflow"] > 0


def test_monthly_totals_endpoint(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/monthly-totals").json()
    assert resp == [{"month": "2026-05", "inflow": resp[0]["inflow"], "outflow": resp[0]["outflow"]}]
    assert resp[0]["outflow"] > 0


def test_dashboard_category_breakdown_sums_to_total_outflow(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    total = round(sum(s["amount"] for s in resp["category_breakdown"]), 2)
    assert total == resp["metrics"]["total_outflow"]


def test_dashboard_empty_database_does_not_error(client):
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()["metrics"]["total_outflow"] == 0


def test_dashboard_summary_rejects_malformed_month_with_clean_422(client):
    resp = client.get("/api/dashboard/summary", params={"date_from": "2024-13"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_MONTH_FORMAT"

    resp = client.get("/api/dashboard/summary", params={"date_to": "not-a-month"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_MONTH_FORMAT"


def test_dashboard_top_paynow_contacts_shows_display_name_not_raw_description(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    paynow_names = [e["name"] for e in resp["top_paynow_contacts"]]
    assert paynow_names  # sample data has at least one PayNow-marker transaction
    for name in paynow_names:
        assert not name.startswith("PayNow to ")  # prefix stripped for the contact list
        assert "PIB" not in name.upper() and "PAYNOW" not in name.upper()  # not the raw bank text
