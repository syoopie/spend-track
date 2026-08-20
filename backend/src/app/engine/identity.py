import hashlib


def derive_account_id(bank_name: str, account_number: str) -> str:
    """Deterministic id so re-uploading a statement for the same account
    resolves to the same `accounts` row, without storing the unmasked
    account number as the primary key itself."""
    payload = f"{bank_name.upper()}|{account_number}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]
