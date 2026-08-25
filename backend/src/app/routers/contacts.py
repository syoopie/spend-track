import csv
import io
import sqlite3
from collections import defaultdict

from fastapi import APIRouter, File, UploadFile

from app import contact_directory, rule_catalog
from app.db import get_conn
from app.errors import not_found_error
from app.models import ContactCreateRequest, ContactImportResult, ContactOut, ContactUpdateRequest

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _fetch_contact(conn: sqlite3.Connection, contact_id: int) -> ContactOut:
    c = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    if c is None:
        raise not_found_error("contact", "CONTACT_NOT_FOUND")
    identifiers = [
        r["identifier"]
        for r in conn.execute(
            "SELECT identifier FROM contact_identifiers WHERE contact_id = ?", (contact_id,)
        ).fetchall()
    ]
    spend_row = conn.execute(
        "SELECT COALESCE(SUM(-amount), 0) AS spend FROM transactions "
        "WHERE contact_id = ? AND amount < 0 AND is_excluded = 0",
        (contact_id,),
    ).fetchone()
    received_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS received FROM transactions "
        "WHERE contact_id = ? AND amount > 0 AND is_excluded = 0",
        (contact_id,),
    ).fetchone()
    return ContactOut(
        id=c["id"],
        name=c["name"],
        default_category_outflow=c["default_category_outflow"],
        default_category_inflow=c["default_category_inflow"],
        default_subcategory=c["default_subcategory"],
        identifiers=identifiers,
        historical_spend=spend_row["spend"],
        historical_received=received_row["received"],
    )


@router.get("", response_model=list[ContactOut])
def list_contacts():
    """Bulk-fetches identifiers/spend in 2 queries instead of _fetch_contact's
    3-per-contact - listing N contacts used to be 1+3N queries."""
    with get_conn() as conn:
        contacts = conn.execute("SELECT * FROM contacts ORDER BY name").fetchall()

        identifiers_by_contact: dict[int, list[str]] = defaultdict(list)
        for r in conn.execute("SELECT contact_id, identifier FROM contact_identifiers").fetchall():
            identifiers_by_contact[r["contact_id"]].append(r["identifier"])

        spend_by_contact: dict[int, float] = defaultdict(float)
        for r in conn.execute(
            "SELECT contact_id, COALESCE(SUM(-amount), 0) AS spend FROM transactions "
            "WHERE contact_id IS NOT NULL AND amount < 0 AND is_excluded = 0 GROUP BY contact_id"
        ).fetchall():
            spend_by_contact[r["contact_id"]] = r["spend"]

        received_by_contact: dict[int, float] = defaultdict(float)
        for r in conn.execute(
            "SELECT contact_id, COALESCE(SUM(amount), 0) AS received FROM transactions "
            "WHERE contact_id IS NOT NULL AND amount > 0 AND is_excluded = 0 GROUP BY contact_id"
        ).fetchall():
            received_by_contact[r["contact_id"]] = r["received"]

        return [
            ContactOut(
                id=c["id"],
                name=c["name"],
                default_category_outflow=c["default_category_outflow"],
                default_category_inflow=c["default_category_inflow"],
                default_subcategory=c["default_subcategory"],
                identifiers=identifiers_by_contact.get(c["id"], []),
                historical_spend=spend_by_contact.get(c["id"], 0.0),
                historical_received=received_by_contact.get(c["id"], 0.0),
            )
            for c in contacts
        ]


@router.post("", response_model=ContactOut)
def create_contact(body: ContactCreateRequest):
    with get_conn() as conn:
        contact_id = contact_directory.insert_contact(
            conn,
            name=body.name,
            default_category_outflow=body.default_category_outflow,
            default_category_inflow=body.default_category_inflow,
            default_subcategory=body.default_subcategory,
            identifiers=body.identifiers,
        )
        return _fetch_contact(conn, contact_id)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, body: ContactUpdateRequest):
    with get_conn() as conn:
        existing = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if existing is None:
            raise not_found_error("contact", "CONTACT_NOT_FOUND")
        name = body.name if body.name is not None else existing["name"]
        subcategory = (
            body.default_subcategory if body.default_subcategory is not None else existing["default_subcategory"]
        )
        outflow = (
            None
            if body.clear_default_category_outflow
            else (
                body.default_category_outflow
                if body.default_category_outflow is not None
                else existing["default_category_outflow"]
            )
        )
        inflow = (
            None
            if body.clear_default_category_inflow
            else (
                body.default_category_inflow
                if body.default_category_inflow is not None
                else existing["default_category_inflow"]
            )
        )
        conn.execute(
            "UPDATE contacts SET name = ?, default_category_outflow = ?, default_category_inflow = ?, "
            "default_subcategory = ? WHERE id = ?",
            (name, outflow, inflow, subcategory, contact_id),
        )
        if body.identifiers is not None:
            contact_directory.replace_contact_identifiers(conn, contact_id, body.identifiers)
        return _fetch_contact(conn, contact_id)


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))


@router.post("/import", response_model=ContactImportResult)
async def import_contacts_csv(file: UploadFile = File(...)):
    """Generic 3-column CSV: Name, Identifier, Category. Unrelated to bank
    statement CSV ingestion (out of scope for this pass) - this just maps
    people to PayNow identifiers in bulk."""
    content = (await file.read()).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(content)))
    if rows and [c.strip().lower() for c in rows[0][:3]] == ["name", "identifier", "category"]:
        rows = rows[1:]

    created = 0
    updated = 0
    with get_conn() as conn:
        for row in rows:
            if len(row) < 3:
                continue
            name, identifier, category = (c.strip() for c in row[:3])
            if not name or not identifier:
                continue

            if contact_directory.find_contact_id_by_identifier(conn, identifier) is not None:
                continue  # identifier already mapped to some contact - leave as-is

            existing_contact = conn.execute(
                "SELECT id FROM contacts WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()
            if existing_contact:
                contact_id = existing_contact["id"]
                updated += 1
                conn.execute(
                    "INSERT INTO contact_identifiers (contact_id, identifier) VALUES (?, ?)",
                    (contact_id, identifier),
                )
            else:
                resolved_category = category or "Others"
                direction = rule_catalog.category_direction(conn, resolved_category)
                contact_directory.insert_contact(
                    conn,
                    name=name,
                    default_category_outflow=resolved_category if direction == "outflow" else None,
                    default_category_inflow=resolved_category if direction == "inflow" else None,
                    identifiers=[identifier],
                )
                created += 1

    return ContactImportResult(contacts_created=created, contacts_updated=updated)
