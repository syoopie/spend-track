import json
import os
from pathlib import Path

# Computed fresh on every call (not cached at import time) so that setting
# SG_TRACKER_HOME via monkeypatch/env in tests takes effect immediately,
# rather than only for the first process ever to import this module.
def _config_dir() -> Path:
    override = os.environ.get("SG_TRACKER_HOME")
    if override:
        return Path(override)
    # get_db_path() already isolates the DB itself per-test via
    # SG_TRACKER_DB_PATH, but config.json (AI settings, etc.) has no such
    # per-key override - without this, any test that touches AI settings
    # (which upload_statement now does on every call, to check ai_enabled)
    # would read/write the real ~/.sg-expenditure-tracker/config.json. This
    # is the same class of leak the relocate test already hit once for
    # db_path itself (see CLAUDE.md) - piggyback config.json's location on
    # the isolated DB path's own directory whenever one is set.
    db_override = os.environ.get("SG_TRACKER_DB_PATH")
    if db_override:
        return Path(db_override).parent
    return Path.home() / ".sg-expenditure-tracker"


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
    override = os.environ.get("SG_TRACKER_DB_PATH")
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
