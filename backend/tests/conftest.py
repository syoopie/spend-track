import pytest

from app.engine import recategorize_job
from app.engine.staging_store import get_store


@pytest.fixture(autouse=True)
def _reset_staging_store():
    """get_store() is a process-wide singleton (see staging_store.py), so a
    batch left pending by one test would otherwise block every upload in
    every test that runs after it in the same pytest session."""
    get_store().reset()
    yield
    get_store().reset()


@pytest.fixture(autouse=True)
def _reset_recategorize_job():
    """Same reasoning as _reset_staging_store - engine/recategorize_job.py
    is also a process-wide singleton."""
    recategorize_job.reset()
    yield
    recategorize_job.reset()
