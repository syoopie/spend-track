import json
import os
from pathlib import Path

# Computed fresh on every call (not cached at import time) so that setting
# SG_TRACKER_HOME via monkeypatch/env in tests takes effect immediately,
# rather than only for the first process ever to import this module.
def _config_dir() -> Path:
    return Path(os.environ.get("SG_TRACKER_HOME", Path.home() / ".sg-expenditure-tracker"))


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
