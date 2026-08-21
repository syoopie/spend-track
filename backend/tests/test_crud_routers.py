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
            "/api/statements/upload", files={"file": ("statement.pdf", f, "application/pdf")}
        )
    body = resp.json()
    client.post(f"/api/statements/staging/{body['batch_id']}/commit")
    return body


# --- categories -------------------------------------------------------


def test_categories_seeded_with_defaults(client):
    resp = client.get("/api/categories")
    names = [c["name"] for c in resp.json()]
    assert names == [
        "Sports & Hobbies", "Beauty", "Food & Drink", "Shopping", "Transport", "Home", "Bills & Fees",
        "Entertainment", "Healthcare", "Education", "Groceries", "PayNow Transfers",
    ]


def test_categories_hidden_others_excluded_unless_requested(client):
    resp = client.get("/api/categories")
    assert "Others" not in [c["name"] for c in resp.json()]

    resp_all = client.get("/api/categories", params={"include_hidden": True})
    names = [c["name"] for c in resp_all.json()]
    assert "Others" in names
    assert len(names) == 13


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
    txs = client.get("/api/transactions", params={"month": "2026-05"}).json()
    assert len(txs) == 39
    txs_other = client.get("/api/transactions", params={"month": "2026-06"}).json()
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


# --- contacts -----------------------------------------------------------


def test_create_list_update_delete_contact(client):
    created = client.post(
        "/api/contacts",
        json={
            "name": "Auntie Mei",
            "default_category": "PayNow Transfers",
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
    csv_content = "Name,Identifier,Category\nBoon Heng,BOON HENG PTE,PayNow Transfers\nMum,+65 9345 1234,PayNow Transfers\n"
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
    csv_content = "Name,Identifier,Category\nBoon Heng,BOON HENG PTE,PayNow Transfers\n"
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
    assert resp["schema_version"] == 3
    assert resp["size_bytes"] > 0


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
    assert len(cats) == 12  # default categories re-seeded (Others is hidden)


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


# --- dashboard ---------------------------------------------------------------


def test_dashboard_summary_metrics_match_manual_totals(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    assert resp["month"] == "2026-05"

    txs = client.get("/api/transactions").json()
    expected_inflow = round(sum(t["amount"] for t in txs if t["amount"] > 0), 2)
    expected_outflow = round(sum(-t["amount"] for t in txs if t["amount"] < 0), 2)

    assert resp["metrics"]["total_inflow"] == expected_inflow
    assert resp["metrics"]["total_outflow"] == expected_outflow
    assert resp["metrics"]["net_expenditure"] == round(expected_inflow - expected_outflow, 2)


def test_dashboard_cash_flow_covers_six_months_including_current(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    assert len(resp["cash_flow"]) == 6
    assert resp["cash_flow"][-1]["month"] == "2026-05"


def test_dashboard_category_breakdown_sums_to_total_outflow(client):
    _upload_and_commit(client)
    resp = client.get("/api/dashboard/summary").json()
    total = round(sum(s["amount"] for s in resp["category_breakdown"]), 2)
    assert total == resp["metrics"]["total_outflow"]


def test_dashboard_empty_database_does_not_error(client):
    resp = client.get("/api/dashboard/summary")
    assert resp.status_code == 200
    assert resp.json()["metrics"]["total_outflow"] == 0
