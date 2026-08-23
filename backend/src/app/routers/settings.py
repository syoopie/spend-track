"""The Settings overview: the one endpoint that aggregates localization,
AI-configuration, and database-file info into a single snapshot for the
Settings page's initial load. AI provider configuration itself lives in
routers/ai_settings.py (`/api/ai/*`); Relocate/Reset/scoped-deletes live in
routers/data_lifecycle.py (`/api/data-lifecycle/*`). `build_settings_out` is
exported so data_lifecycle.py's relocate endpoint can return the same
snapshot shape after moving the DB file.
"""

from pathlib import Path

from fastapi import APIRouter

from app.config import get_ai_settings, get_db_path
from app.db import get_conn
from app.localization import ACTIVE_COUNTRY
from app.models import SettingsOut
from app.routers.ai_settings import redact_ai_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _schema_version(db_path: Path) -> int:
    with get_conn() as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def _localization_fields() -> dict:
    return {
        "country_code": ACTIVE_COUNTRY.code,
        "country_name": ACTIVE_COUNTRY.name,
        "currency_code": ACTIVE_COUNTRY.currency_code,
        "currency_symbol": ACTIVE_COUNTRY.currency_symbol,
        "transfer_scheme_name": ACTIVE_COUNTRY.transfer_scheme_name,
        "supported_banks": [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers],
    }


def build_settings_out(db_path: Path) -> SettingsOut:
    size = db_path.stat().st_size if db_path.exists() else 0
    return SettingsOut(
        db_path=str(db_path),
        size_bytes=size,
        schema_version=_schema_version(db_path),
        **_localization_fields(),
        **redact_ai_settings(get_ai_settings()),
    )


@router.get("", response_model=SettingsOut)
def get_settings():
    return build_settings_out(get_db_path())
