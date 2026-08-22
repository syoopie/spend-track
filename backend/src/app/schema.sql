-- Informational only, surfaced read-only via GET /api/settings - actual
-- migrations are driven by db.py's _add_column_if_missing column-existence
-- checks, not by gating on this number. Bump it as a human-readable trail
-- of schema changes, but don't wire new migration logic to it.
PRAGMA user_version = 6;

CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    bank_name TEXT NOT NULL,
    account_number_masked TEXT NOT NULL,
    account_type TEXT NOT NULL,
    is_card BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    default_category TEXT NOT NULL,
    default_subcategory TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contact_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    identifier TEXT UNIQUE NOT NULL, -- Phone, UEN, or Account Number
    FOREIGN KEY(contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    priority INTEGER DEFAULT 1,
    match_pattern TEXT NOT NULL,
    target_category TEXT NOT NULL,
    target_subcategory TEXT,
    is_exclusion_rule BOOLEAN DEFAULT 0,
    exclusion_reason TEXT,
    direction TEXT NOT NULL DEFAULT 'outflow',
    is_default BOOLEAN DEFAULT 0,
    display_label TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE NOT NULL,
    account_id TEXT NOT NULL,
    transaction_date TEXT NOT NULL,
    raw_description TEXT NOT NULL,
    cleaned_description TEXT,
    matched_label TEXT,
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

CREATE TABLE IF NOT EXISTS refund_pairings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_transaction_id INTEGER NOT NULL,
    refund_transaction_id INTEGER NOT NULL,
    FOREIGN KEY(original_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY(refund_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
);

-- Not in the original TECHNICAL_SPEC.md schema: added so the mockup's fixed
-- category list is extensible later (add/rename) without a migration.
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    hue INTEGER,
    icon TEXT,
    is_hidden BOOLEAN DEFAULT 0,
    sort_order INTEGER DEFAULT 0,
    -- 'inflow' or 'outflow' - a category is locked to one direction, never
    -- both. See engine/rules.py::categorize() for how this is enforced.
    direction TEXT NOT NULL DEFAULT 'outflow'
);

CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_tx_fingerprint ON transactions(fingerprint);
CREATE INDEX IF NOT EXISTS idx_rule_priority ON rules(priority);
