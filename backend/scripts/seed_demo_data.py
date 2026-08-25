"""Rebuild the demo database the README screenshots are taken from.

Everything here is the committed synthetic sample data in
`PDF Examples (Sanitized)/` plus placeholder contacts and rules - no real
statement, name, phone number or UEN is involved. The two identifiers that
look like a phone number and a UEN are deliberately invalid (a Singapore
mobile never starts with 0), so they can't collide with a real person while
still showing the shape the contacts feature is for.

Usage - with the backend running against a throwaway database:

    SPENDTRACK_DB_PATH=/tmp/demo.db uv run uvicorn app.main:app --port 8000
    uv run python scripts/seed_demo_data.py

Contacts and rules are created *before* the upload on purpose: categorization
runs at upload time, so a contact added afterwards would own no transactions
and show $0 historical spend.
"""

from __future__ import annotations

import glob
import io
import json
import os
import urllib.request
from pathlib import Path

API = os.environ.get("SPENDTRACK_API", "http://127.0.0.1:8000/api")
SAMPLES = Path(__file__).resolve().parents[2] / "PDF Examples (Sanitized)" / "UOB"

CONTACTS = [
    ("Sample Payee A", ["SAMPLE PAYEE A", "+65 0000 0001"], "Paynow"),
    ("Sample Payee B", ["SAMPLE PAYEE B"], "Paynow"),
    ("Sample Payee C", ["SAMPLE PAYEE C"], "Paynow"),
    ("Sample Payee D", ["SAMPLE PAYEE D"], "Paynow"),
    ("Sample Payee E", ["SAMPLE PAYEE E"], "Paynow"),
    ("Sample Renovation LLP", ["SAMPLE RENOVATION LLP", "UEN 000000000A"], "Home"),
]

RULES = [
    {"match_pattern": "SAMPLE EMPLOYER PTE LTD", "target_category": "Salary", "display_label": "Monthly Salary"},
    {"match_pattern": "TOWN COUNCIL CONSERVANCY", "target_category": "Bills & Fees", "display_label": "Conservancy Fees"},
    {"match_pattern": "SAMPLE ONLINE STORE", "target_category": "Shopping", "display_label": "Sample Online Store"},
    {"match_pattern": "SAMPLE AIRLINE BOOKING", "target_category": "Entertainment", "display_label": "Flights"},
    {"match_pattern": "SP GROUP", "target_category": "Bills & Fees", "display_label": "Electricity"},
    {
        "match_pattern": "TO SAMPLE SAVINGS ACCOUNT",
        "is_exclusion_rule": True,
        "direction": "outflow",
        "exclusion_reason": "Moving money between my own accounts",
    },
]


def get(path: str):
    with urllib.request.urlopen(API + path) as r:
        return json.load(r)


def post(path: str, payload: dict):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def upload(paths: list[str]):
    boundary = "----sgtrackerdemoboundary"
    body = io.BytesIO()
    for p in paths:
        body.write(f"--{boundary}\r\n".encode())
        body.write(
            f'Content-Disposition: form-data; name="files"; filename="{os.path.basename(p)}"\r\n'.encode()
        )
        body.write(b"Content-Type: application/pdf\r\n\r\n")
        body.write(Path(p).read_bytes())
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        API + "/statements/upload",
        data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main() -> None:
    if get("/transactions"):
        raise SystemExit("This database already has transactions - point SPENDTRACK_DB_PATH at an empty one.")

    for name, identifiers, category in CONTACTS:
        post("/contacts", {"name": name, "identifiers": identifiers, "default_category": category})
    for rule in RULES:
        post("/rules", rule)

    files = sorted(glob.glob(f"{SAMPLES}/Account Statements/*.pdf")) + sorted(
        glob.glob(f"{SAMPLES}/Card Statements/*.pdf")
    )
    batch = upload(files)
    result = post(f"/statements/staging/{batch['batch_id']}/commit", {})
    print(
        f"{len(files)} statements -> {result['transactions_committed']} transactions, "
        f"{result['accounts_provisioned']} accounts, {result['refund_pairs_created']} refund pairs, "
        f"{len(CONTACTS)} contacts, {len(RULES)} rules"
    )


if __name__ == "__main__":
    main()
