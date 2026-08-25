import json
import os
from pathlib import Path

#: The app was called "SG Expenditure Tracker" before it was clear the
#: parser layer generalizes past one country. Both spellings of every
#: environment variable are honoured, new name first, so a script or shell
#: profile written against the old name keeps working indefinitely - there
#: is no deprecation date here and no warning to act on.
_ENV_ALIASES = {
    "home": ("SPENDTRACK_HOME", "SG_TRACKER_HOME"),
    "db_path": ("SPENDTRACK_DB_PATH", "SG_TRACKER_DB_PATH"),
}

LEGACY_CONFIG_DIR_NAME = ".sg-expenditure-tracker"
CONFIG_DIR_NAME = ".spendtrack"


def env_override(key: str) -> str | None:
    """First of this setting's environment variable spellings that is set."""
    for name in _ENV_ALIASES[key]:
        value = os.environ.get(name)
        if value:
            return value
    return None


# Computed fresh on every call (not cached at import time) so that setting
# SPENDTRACK_HOME via monkeypatch/env in tests takes effect immediately,
# rather than only for the first process ever to import this module.
def _config_dir() -> Path:
    override = env_override("home")
    if override:
        return Path(override)
    # get_db_path() already isolates the DB itself per-test via
    # SPENDTRACK_DB_PATH, but config.json (AI settings, etc.) has no such
    # per-key override - without this, any test that touches AI settings
    # (which upload_statement now does on every call, to check ai_enabled)
    # would read/write the real ~/.spendtrack/config.json. This is the same
    # class of leak the relocate test already hit once for db_path itself
    # (see CLAUDE.md) - piggyback config.json's location on the isolated DB
    # path's own directory whenever one is set.
    db_override = env_override("db_path")
    if db_override:
        return Path(db_override).parent

    # An existing install keeps its directory. Moving someone's database
    # during a rename is a bigger risk than a directory named after the old
    # brand, and config.json can hold an absolute db_path pointing inside
    # it - so the old location wins whenever it's the one that exists.
    home = Path.home()
    legacy = home / LEGACY_CONFIG_DIR_NAME
    if legacy.is_dir() and not (home / CONFIG_DIR_NAME).is_dir():
        return legacy
    return home / CONFIG_DIR_NAME


def _config_file() -> Path:
    return _config_dir() / "config.json"


def _default_db_path() -> Path:
    return _config_dir() / "data.db"


def _read_config() -> dict:
    config_file = _config_file()
    if config_file.exists():
        return json.loads(config_file.read_text())
    return {}


def _write_config(cfg: dict) -> None:
    _config_dir().mkdir(parents=True, exist_ok=True)
    _config_file().write_text(json.dumps(cfg, indent=2))


def get_db_path() -> Path:
    override = env_override("db_path")
    if override:
        return Path(override)
    cfg = _read_config()
    path = cfg.get("db_path")
    return Path(path) if path else _default_db_path()


def set_db_path(path: Path) -> None:
    cfg = _read_config()
    cfg["db_path"] = str(path)
    _write_config(cfg)


_AI_DEFAULTS = {
    "ai_enabled": False,
    "ai_provider": "ollama",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "",
    "openai_api_key": "",
    "anthropic_model": "",
    "anthropic_api_key": "",
}


def get_ai_settings() -> dict:
    cfg = _read_config()
    return {key: cfg.get(key, default) for key, default in _AI_DEFAULTS.items()}


def set_ai_settings(**updates) -> dict:
    """Partial update - only keys present in `updates` (and not None) are
    changed; everything else keeps its current stored (or default) value.
    Unknown keys are ignored rather than raising, so callers can pass
    through a full request body without pre-filtering it."""
    cfg = _read_config()
    for key, value in updates.items():
        if key in _AI_DEFAULTS and value is not None:
            cfg[key] = value
    _write_config(cfg)
    return get_ai_settings()
