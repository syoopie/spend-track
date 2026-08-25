"""Where the app keeps its data, across the rename.

The app used to be called "SG Expenditure Tracker" and stored everything in
`~/.sg-expenditure-tracker`. Renaming it must not strand an existing
install's database, and must not break a script written against the old
environment variable names - neither failure would be loud.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    for names in config._ENV_ALIASES.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("var", ["SPENDTRACK_DB_PATH", "SG_TRACKER_DB_PATH"])
def test_both_spellings_of_the_db_path_variable_work(monkeypatch, tmp_path, var):
    monkeypatch.setenv(var, str(tmp_path / "data.db"))
    assert config.get_db_path() == tmp_path / "data.db"


@pytest.mark.parametrize("var", ["SPENDTRACK_HOME", "SG_TRACKER_HOME"])
def test_both_spellings_of_the_home_variable_work(monkeypatch, tmp_path, var):
    monkeypatch.setenv(var, str(tmp_path))
    assert config._config_dir() == tmp_path


def test_the_new_name_wins_when_both_are_set(monkeypatch, tmp_path):
    monkeypatch.setenv("SPENDTRACK_HOME", str(tmp_path / "new"))
    monkeypatch.setenv("SG_TRACKER_HOME", str(tmp_path / "old"))
    assert config._config_dir() == tmp_path / "new"


def test_a_fresh_install_uses_the_new_directory(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert config._config_dir() == tmp_path / config.CONFIG_DIR_NAME


def test_an_existing_install_keeps_its_old_directory(monkeypatch, tmp_path):
    """Moving someone's database during a rename risks more than a
    directory named after the old brand - config.json can hold an absolute
    db_path pointing inside it."""
    (tmp_path / config.LEGACY_CONFIG_DIR_NAME).mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert config._config_dir() == tmp_path / config.LEGACY_CONFIG_DIR_NAME


def test_the_new_directory_wins_once_it_exists(monkeypatch, tmp_path):
    """Both present means someone has already moved across (or started
    fresh alongside an old install) - the new one is the live copy."""
    (tmp_path / config.LEGACY_CONFIG_DIR_NAME).mkdir()
    (tmp_path / config.CONFIG_DIR_NAME).mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert config._config_dir() == tmp_path / config.CONFIG_DIR_NAME
