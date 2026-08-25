# SpendTrack (backend)

FastAPI + SQLite backend for SpendTrack, the local-first bank statement tracker. See the [repo root README](../README.md) for the full picture (what it does, one-command startup, design decisions).

```bash
uv sync
uv run uvicorn app.main:app --reload   # http://127.0.0.1:8000
uv run pytest                          # run the test suite
```
