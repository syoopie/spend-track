# System Architecture & Technical Specification

## 1. System Execution Topology

* **Distribution & Runtime:** Single CLI executable (`uvx expenditure-tracker`) running FastAPI and Uvicorn bound locally to `127.0.0.1:8000`.
* **Frontend Bundle:** Static React + Tailwind SPA compiled into the backend binary and opened via Python's `webbrowser` module.
* **Data Storage:** Unencrypted local SQLite database managed by the OS user account access permissions.

---

## 2. Ingestion & Multi-Page Parsing Pipeline

```
[ File Upload Stream ]
         │
         ▼
( Encrypted PDF? ) ──YES──► [ In-Memory Password Decryption ]
         │
        NO
         │
         ▼
[ Bank Anchor Detection ] (DBS / OCBC / UOB)
         │
         ▼
[ Spatial Line-Buffer Extraction ]
  ├─ Multi-line concatenation via Y-axis bounding boxes
  └─ Header/Footer & Page-break suppression
         │
         ▼
[ Transaction Normalization & Refund Netting ]

```

### Parsing Mechanics

* **Format Failures:** If a PDF cannot be parsed due to unknown bank formatting, the API raises an unhandled parse error (`HTTP 422: UNPARSEABLE_STATEMENT_FORMAT`). No manual column-mapping UI fallback is provided.
* **Multi-Page Line Resolution:** Line buffers evaluate vertical distance ($Y$-coordinates). Description strings wrapping across page boundaries are concatenated into the preceding transaction record before generating hashes.
* **Currency Standardization:** Only final SGD settlement amounts are extracted. Foreign currency values and exchange rates are omitted.

---

## 3. Idempotency & Deterministic Hashing

To prevent duplicates when re-uploading overlapping monthly statements, transactions are processed through SHA-256 fingerprinting.

$$\text{Fingerprint} = \text{SHA256}(\text{account\_id} \parallel \text{date} \parallel \text{amount} \parallel \text{cleaned\_description} \parallel \text{daily\_sequence\_index})$$

* **Daily Sequence Index:** Computed by calculating the zero-indexed appearance count of identical transactions (same date, amount, and description) within a single statement file.

---

## 4. Priority-Based Rules & Netting Engine

### Rule Evaluation Order

Transactions pass through the rules engine strictly ordered by the user-assigned `priority` attribute:

```
[ New Transaction ]
        │
        ▼
[ Query Active Rules ORDER BY priority ASC ]
        │
        ├─► Priority 1 Match? ──YES──► Apply Category/Exclusion & Stop
        ├─► Priority 2 Match? ──YES──► Apply Category/Exclusion & Stop
        └─► No Match ───────────────► Fallback to Contact Match or 'Others'

```

### Refund Linkage Algorithm

During ingestion, positive amount transactions (Inflows) matching a previous negative amount transaction (Outflow) with identical merchant string patterns are linked via a `refund_pairings` record:

```sql
INSERT INTO refund_pairings (original_transaction_id, refund_transaction_id)
SELECT t1.id, t2.id
FROM transactions t1
JOIN transactions t2 
  ON t1.account_id = t2.account_id 
 AND t1.amount = -t2.amount
 AND t2.transaction_date >= t1.transaction_date
WHERE t1.amount < 0 AND t2.amount > 0;

```

---

## 5. Storage Schema (SQLite)

```sql
PRAGMA user_version = 2;

CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL,
    account_number_masked TEXT NOT NULL,
    account_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    default_category TEXT NOT NULL,
    default_subcategory TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE contact_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    identifier TEXT UNIQUE NOT NULL, -- Phone, UEN, or Account Number
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority INTEGER DEFAULT 1,
    match_pattern TEXT NOT NULL,
    target_category TEXT NOT NULL,
    target_subcategory TEXT,
    is_exclusion_rule BOOLEAN DEFAULT 0,
    exclusion_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE NOT NULL,
    account_id TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    raw_description TEXT NOT NULL,
    cleaned_description TEXT,
    amount REAL NOT NULL,
    category TEXT DEFAULT 'Others',
    subcategory TEXT DEFAULT 'Unparsable',
    contact_id INTEGER,
    is_excluded BOOLEAN DEFAULT 0,
    exclusion_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE SET NULL
);

CREATE TABLE refund_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_transaction_id INTEGER NOT NULL,
    refund_transaction_id INTEGER NOT NULL,
    FOREIGN KEY(original_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY(refund_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
);

CREATE INDEX idx_tx_date ON transactions(transaction_date);
CREATE INDEX idx_tx_fingerprint ON transactions(fingerprint);
CREATE INDEX idx_rule_priority ON rules(priority);

```

---

## 6. Database Relocation Protocol

When a user triggers a database relocation in Settings:

1. System queries database size (`SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size();`).
2. API opens a transaction lock and closes active SQLite file handles.
3. System copies `data.db`, `data.db-wal`, and `data.db-shm` to the target directory.
4. Old files are removed, and the local path configuration file (`~/.sg-expenditure-tracker/config.json`) updates to point to the new location.