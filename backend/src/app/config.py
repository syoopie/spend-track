import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("SG_TRACKER_HOME", Path.home() / ".sg-expenditure-tracker"))
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_DB_PATH = CONFIG_DIR / "data.db"


def _read_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def _write_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_db_path() -> Path:
    override = os.environ.get("SG_TRACKER_DB_PATH")
    if override:
        return Path(override)
    cfg = _read_config()
    path = cfg.get("db_path")
    return Path(path) if path else DEFAULT_DB_PATH


def set_db_path(path: Path) -> None:
    cfg = _read_config()
    cfg["db_path"] = str(path)
    _write_config(cfg)
