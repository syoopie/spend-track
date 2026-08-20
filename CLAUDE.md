# Notes for Claude Code

Non-obvious stuff learned while building this. Don't re-derive these the hard way.

## UOB PDF parsing (`backend/src/app/parsing/uob/`)

- These statements have **no table gridlines** — columns are pure whitespace alignment. Don't reach for `pdfplumber.extract_table()`; it needs ruling lines. Instead: cluster words into physical lines by `top` proximity (`pdf_utils.group_into_lines`), then bucket each line's words into columns by hardcoded x-ranges calibrated against the real samples (see `pdf_utils.Column`).
- **Every page has a bilingual disclaimer footer** whose words fall inside the description column's x-range (e.g. "UOB Plaza Singapore" lands at x0≈128, inside the 100–330 description bucket). If you don't filter words by `top < FOOTER_TOP_CUTOFF` (780) *before* grouping into lines, footer text silently gets appended to whatever transaction was last on the page. This was a real bug — caught it by grepping parsed output for `"relation thereto"`.
- **Card statement `SUB TOTAL` is a running balance, not this statement's net.** It equals `PREVIOUS BALANCE + charges − credits`, not `charges − credits` alone. If you're cross-validating a parser against the printed total, you must include `PREVIOUS BALANCE` in the formula or every multi-month sample will look "wrong" when it isn't.
- **Card identity line vs. Summary table is a real false-positive trap.** The per-card `Summary` table near the top of page 1 also contains the card number as its own word — a naive "any line matching the card-number regex is the identity line" grabs the Summary row (wrong card name) instead of the true per-card identity line right above the transaction table. Fix: only resolve identity by searching *backward* from a confirmed `Post`/`Trans` header line, never by scanning forward for the number pattern.
- Account statement dates have no year (`"05 May"`) — derived from the `Period: ... to ...` line. Card statement dates have no year either (`"10 JUN"`) — derived from `Statement Date`, with `year -= 1` when a transaction's month is later than the statement's month (Dec/Jan wraparound).
- `BALANCE B/F`, `Total` (account statements) and `PREVIOUS BALANCE`, `SUB TOTAL`, `TOTAL BALANCE FOR ...` (card statements) are not transactions — they're excluded by exact-prefix text match, not by column heuristics.

## Schema quirk

`rules.target_category` is `NOT NULL` in the spec's schema even though exclusion rules don't logically use it. Creating an exclusion rule without a category will hit an `IntegrityError` unless you default it (the API defaults to `"Others"` — see `routers/rules.py::create_rule`).

## Design deviations from `TECHNICAL_SPEC.md` (intentional, not oversights)

- **Staging is in-memory** (`engine/staging_store.py`), not a DB table — the spec's schema has none, and pre-commit review is inherently transient. A batch is lost if the server restarts before commit.
- **Refund pairing is not amount-only.** The literal SQL in the spec (`t1.amount = -t2.amount`) would mass-false-positive on any two unrelated transactions of equal-and-opposite amount. Pairing also requires merchant-name similarity after stripping suffix tokens like REFUND/REVERSAL (see `engine/refunds.py`).
- **`categories` table exists but isn't in the spec's schema** — added purely so the mockup's fixed category list is extensible later without a migration.

## Dev workflow gotchas (Windows / this environment)

- **`pkill -f "uvicorn app.main:app"` does not reliably kill a `uv run`-wrapped server on Windows/Git Bash** — `uv run` spawns a child process with a different command line, so the pattern doesn't match and the old server keeps holding the port. Symptom: a fresh `--reload` server logs `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions` and silently fails to bind, while the *old* process keeps serving stale code. Find the real PID with `netstat -ano | grep ":8000" | grep LISTENING` and kill it with `powershell -Command "Stop-Process -Id <PID> -Force"`.
- **DB path env vars behave differently.** `SG_TRACKER_DB_PATH` is re-read on every call (safe to set per-test). `SG_TRACKER_HOME` is only read once at import time to compute `CONFIG_DIR` — setting it after the process has started does nothing. Use `SG_TRACKER_DB_PATH` for test isolation; only use `SG_TRACKER_HOME` when specifically testing the config.json-driven relocate flow, and set it before the process starts.
- **`uv_build` needs explicit module-name config** for a `src/app` layout that doesn't match the project name: `[tool.uv.build-backend] module-name = "app"` in `pyproject.toml`. Without it, `uv init`'s default (`src/expenditure_tracker`) is what gets built.
- This project's installed FastAPI version wraps included routers in an internal `_IncludedRouter` — iterating `app.routes` won't show flattened sub-routes for introspection/debugging. Verify routes actually work by hitting them (TestClient or curl), not by inspecting `app.routes`.

## Browser-automation testing gotchas (claude-in-chrome)

- The `form_input` tool setting a checkbox's value **does not reliably fire React's synthetic `onChange`** — state silently stays stale even though the tool reports success. Use a real `computer` mouse click on checkboxes when testing React-controlled inputs; `form_input` is fine for `<select>` and text inputs.
- Native HTML5 `draggable`/`ondragstart`/`ondrop` (used for rule priority reordering) isn't triggered by the `left_click_drag` action — it needs real DOM drag events a synthetic mouse drag doesn't produce. Verify drag-and-drop-backed features via a direct API call instead of trying to simulate the drag in-browser.
