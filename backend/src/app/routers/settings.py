import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import get_ai_settings, get_db_path, set_ai_settings, set_db_path
from app.db import get_conn, init_db
from app.engine.ai_providers import build_provider
from app.errors import api_error
from app.localization import ACTIVE_COUNTRY
from app.models import (
    AiSettingsOut,
    AiSettingsUpdateRequest,
    AiStatusOut,
    DeleteScopeResult,
    RelocateRequest,
    ResetRequest,
    SettingsOut,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PROVIDER_REQUIREMENTS = {
    "ollama": ("ollama_model", "A model name"),
    "openai_compatible": ("openai_model", "A model name"),
    "anthropic": ("anthropic_model", "A model name"),
}
_PROVIDER_KEY_REQUIREMENTS = {
    "openai_compatible": "openai_api_key",
    "anthropic": "anthropic_api_key",
}


def _redact(ai: dict) -> dict:
    def last4(key: str) -> str | None:
        return key[-4:] if len(key) >= 4 else (key or None)

    return {
        "ai_enabled": ai["ai_enabled"],
        "ai_provider": ai["ai_provider"],
        "ollama_url": ai["ollama_url"],
        "ollama_model": ai["ollama_model"],
        "openai_base_url": ai["openai_base_url"],
        "openai_model": ai["openai_model"],
        "openai_api_key_set": bool(ai["openai_api_key"]),
        "openai_api_key_last4": last4(ai["openai_api_key"]) if ai["openai_api_key"] else None,
        "anthropic_model": ai["anthropic_model"],
        "anthropic_api_key_set": bool(ai["anthropic_api_key"]),
        "anthropic_api_key_last4": last4(ai["anthropic_api_key"]) if ai["anthropic_api_key"] else None,
    }


def _schema_version(db_path: Path) -> int:
    with get_conn() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def _require_delete_confirmation(body: ResetRequest) -> None:
    if body.confirm != "DELETE":
        raise api_error(400, "RESET_CONFIRMATION_MISMATCH", "Type DELETE to confirm.")


def _localization_fields() -> dict:
    return {
        "country_code": ACTIVE_COUNTRY.code,
        "country_name": ACTIVE_COUNTRY.name,
        "currency_code": ACTIVE_COUNTRY.currency_code,
        "currency_symbol": ACTIVE_COUNTRY.currency_symbol,
        "transfer_scheme_name": ACTIVE_COUNTRY.transfer_scheme_name,
        "supported_banks": [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers],
    }


def _settings_out(db_path: Path) -> SettingsOut:
    size = db_path.stat().st_size if db_path.exists() else 0
    return SettingsOut(
        db_path=str(db_path),
        size_bytes=size,
        schema_version=_schema_version(db_path),
        **_localization_fields(),
        **_redact(get_ai_settings()),
    )


@router.get("", response_model=SettingsOut)
def get_settings():
    return _settings_out(get_db_path())


@router.get("/ai/status", response_model=AiStatusOut)
def get_ai_status():
    try:
        provider = build_provider(get_ai_settings())
    except ValueError as exc:
        # Defensive: AiSettingsUpdateRequest.ai_provider is now a Literal, so
        # this can no longer be reached through the API - but a pre-existing
        # or hand-edited config.json could still hold a stale/invalid value,
        # and that should surface as "unreachable", not a 500.
        return AiStatusOut(reachable=False, models=[], error=str(exc))
    health = provider.check_health()
    return AiStatusOut(reachable=health.reachable, models=health.models, error=health.error)


@router.patch("/ai", response_model=AiSettingsOut)
def update_ai_settings(body: AiSettingsUpdateRequest):
    current = get_ai_settings()
    updates = body.model_dump(exclude={"clear_openai_api_key", "clear_anthropic_api_key"}, exclude_none=True)
    # A blank key means "the user didn't type a new one" (the raw key is
    # never echoed back to the frontend, so its input starts empty) - not
    # "clear it". Clearing is only ever the explicit clear_*_api_key flag.
    for key_field in ("openai_api_key", "anthropic_api_key"):
        if not updates.get(key_field):
            updates.pop(key_field, None)
    if body.clear_openai_api_key:
        updates["openai_api_key"] = ""
    if body.clear_anthropic_api_key:
        updates["anthropic_api_key"] = ""

    resulting_provider = updates.get("ai_provider", current["ai_provider"])
    resulting_enabled = updates.get("ai_enabled", current["ai_enabled"])
    if resulting_enabled:
        merged = {**current, **updates}
        # ai_provider on the request is now a Literal, so this can only be
        # reached via a stale/hand-edited config.json still holding an old
        # invalid value - a clean 400 beats a KeyError -> 500.
        requirement = _PROVIDER_REQUIREMENTS.get(resulting_provider)
        if requirement is None:
            raise api_error(
                400, "AI_PROVIDER_NOT_CONFIGURED", f"Unknown AI provider {resulting_provider!r} - re-select a provider."
            )
        model_field, model_label = requirement
        if not merged.get(model_field):
            raise api_error(400, "AI_PROVIDER_NOT_CONFIGURED", f"{model_label} is required for {resulting_provider}.")
        key_field = _PROVIDER_KEY_REQUIREMENTS.get(resulting_provider)
        if key_field and not merged.get(key_field):
            raise api_error(400, "AI_PROVIDER_NOT_CONFIGURED", f"An API key is required for {resulting_provider}.")

    updated = set_ai_settings(**updates)
    return AiSettingsOut(**_redact(updated))


@router.post("/relocate", response_model=SettingsOut)
def relocate_database(body: RelocateRequest):
    """Per TECHNICAL_SPEC.md §6: checkpoint + copy data.db(-wal/-shm) to the
    new location, remove the old files, then repoint config.json."""
    old_path = get_db_path()
    if not old_path.exists():
        raise api_error(404, "DB_NOT_FOUND", "No database file to relocate.")

    new_path = Path(body.new_path)
    if new_path.resolve() == old_path.resolve():
        raise api_error(400, "RELOCATE_SAME_PATH", "New path is the same as the current database path.")
    new_path.parent.mkdir(parents=True, exist_ok=True)

    with get_conn() as conn:
        conn.execute("PRAGMA wal_checkpoint(FULL)")

    for suffix in ("", "-wal", "-shm"):
        src = Path(str(old_path) + suffix)
        if src.exists():
            shutil.copy2(src, Path(str(new_path) + suffix))
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(old_path) + suffix)
        if src.exists():
            src.unlink()

    set_db_path(new_path)
    return _settings_out(new_path)


@router.post("/reset", status_code=204)
def reset_database(body: ResetRequest):
    _require_delete_confirmation(body)
    db_path = get_db_path()
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    init_db(db_path)


@router.post("/delete-rules", response_model=DeleteScopeResult)
def delete_all_rules(body: ResetRequest):
    """Only user-created rules - is_default rules are a pure function of
    default_rules.py and get reconciled back on the next startup anyway, so
    deleting them here would be a no-op that misleads the user about what
    just happened."""
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM rules WHERE is_default = 0")
        return DeleteScopeResult(deleted_count=cur.rowcount)


@router.post("/delete-contacts", response_model=DeleteScopeResult)
def delete_all_contacts(body: ResetRequest):
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM contacts")
        return DeleteScopeResult(deleted_count=cur.rowcount)


@router.post("/delete-transactions", response_model=DeleteScopeResult)
def delete_all_transactions(body: ResetRequest):
    """Accounts are left in place - an account with zero transactions is a
    valid, unremarkable state (e.g. right after this action, or before the
    first statement for it is ever uploaded)."""
    _require_delete_confirmation(body)
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions")
        return DeleteScopeResult(deleted_count=cur.rowcount)
