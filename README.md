<div align="center">

# SG Expenditure Tracker

**Turn your Singapore bank statements into a spending dashboard — on your own computer, with nothing sent anywhere.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Runs locally](https://img.shields.io/badge/data-100%25%20local-brightgreen?style=flat-square)](#your-data-stays-on-your-computer)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](backend/pyproject.toml)
[![React 19](https://img.shields.io/badge/react-19-61dafb?style=flat-square&logo=react&logoColor=white)](frontend/package.json)
[![Banks: UOB](https://img.shields.io/badge/statements-UOB-e35fd0?style=flat-square)](#adding-a-bank)

</div>

Give it a statement PDF you downloaded from your bank, and it reads every transaction, sorts them into categories, cancels out refunds against the purchases they reverse, and shows you where your money actually went.

**Using it** · [Download and run](#download-and-run) · [Try the sample data](#try-it-before-using-your-own-statements) · [The everyday routine](#the-everyday-routine) · [AI categorization](#optional-let-ai-sort-out-the-leftovers) · [Questions](#questions)

**Working on it** · [Adding a bank](#adding-a-bank) · [Run it from source](#run-it-from-source) · [For developers](#for-developers)

![The dashboard: inflow, outflow and net expenditure for the selected months, a cash flow chart, a category breakdown donut, and the searchable transaction feed](docs/screenshots/dashboard.jpg)

## Your data stays on your computer

There is no account to create, no website to log into, and nothing is uploaded. Your transactions live in a single file on your own disk, and the app never talks to your bank — it only reads PDFs you already have. The one exception is the optional AI feature described further down, which stays off unless you switch it on yourself.

## What it does

- **Reads UOB statements** — bank account and credit card e-statements, including password-protected ones. Upload one PDF, or a whole year's worth at once, mixing months and statement types freely. DBS and OCBC are recognized but not read yet: upload one and the app says so plainly instead of guessing. Support for them, and for other banks, is intended — see [Adding a bank](#adding-a-bank).
- **Sorts transactions into categories automatically**, using rules you can see and edit, plus a built-in list of common Singapore merchants. Your own rules always take priority.
- **Lets you check before anything is saved.** Every upload lands in a review screen first, with anything the app wasn't sure about — an unfamiliar PayNow transfer, say — flagged for you to decide.
- **Doesn't double-count.** Uploading the same statement twice is safe: repeats are spotted and skipped. And if you upload both a credit card statement and the bank account that pays that card's bill, the bill payment isn't counted as extra spending on top of the purchases themselves.
- **Nets off refunds** against the original purchase, matching on the merchant name as well as the amount, so two unrelated transactions don't get paired by accident.
- **Names the people you pay.** Save a PayNow number or UEN as a contact once, and future transfers to them are labelled and categorized on their own.
- **Shows you the picture:** money in and out, spending by category, whether you're spending faster than last month, your top merchants and your most-paid PayNow contacts — all filterable by date range and account.

## Download and run

No installers, no accounts, no command line. Grab the file for your computer from the [latest release](https://github.com/syoopie/spend-track/releases/latest), open it, and the app appears in your browser.

| Your computer | Download | How to open it |
|---|---|---|
| **Windows** | `SpendTrack-windows-x86_64.exe` | Double-click it. Windows will warn that the publisher is unknown — click **More info** → **Run anyway**. |
| **Mac** (Apple silicon) | `SpendTrack-macos-arm64.zip` | Unzip, then **right-click** the app → **Open** → **Open**. Double-clicking the first time gives a "cannot be opened" message; right-click → Open is what gets past it. |
| **Linux** | `SpendTrack-linux-x86_64` | `chmod +x SpendTrack-linux-x86_64` once, then run it. |

A small window opens showing where your data is stored and the address the app is running at, and your browser opens on the dashboard. **Closing that window closes the app.** Your data is saved as you go.

<details>
<summary>Why does my computer warn me about it?</summary>

Both warnings mean the same thing: the download isn't signed with a paid developer certificate (Apple charges $99/year, Microsoft rather more). Nothing about the app changes if you get past the warning — but you shouldn't take that on faith from the person who wrote it. Everything here is source code you can read, and the download is built in the open by [this GitHub Actions workflow](.github/workflows/desktop-build.yml), from the exact commit each release names. If you'd rather not run an unsigned binary at all, [run it from source](#run-it-from-source) instead.

</details>

### Try it before using your own statements

You don't need real statements to look around. The folder `PDF Examples (Sanitized)/UOB/` holds a full year of made-up statements for a fictional customer — twelve months of account statements and twelve of credit card statements, 300-odd transactions in all. Select the whole folder and upload it in one go; that's the dataset every screenshot on this page was taken from. They're processed by the same code as a genuine statement, so what you see is the real behaviour, just with invented numbers. When you're done, **Settings** has options to clear everything out.

### The everyday routine

1. **Upload** one or more statement PDFs (button in the sidebar, or drag them onto the window).
2. **Review** how each transaction was categorized, and fix anything that looks off.
3. **Commit** — the transactions join your history.
4. **Explore** the dashboard, filtered by whatever date range and account you care about.

The app has a built-in **User Guide** in the sidebar that walks through each screen in more detail.

## Optional: let AI sort out the leftovers

**Off by default.** If you turn it on under **Settings**, then after each upload the transactions the rules couldn't figure out get sent to an AI model, which suggests a category, a tidy merchant name, and a rule you could save for next time. Nothing is applied behind your back — the suggestions simply show up pre-filled in the review screen for you to accept, edit, or reject. You can close the review screen and come back later; the suggestions will be waiting. If a pass is taking too long, a **Terminate** button appears after 15 seconds and leaves everything exactly as the rules left it.

You choose which model it talks to:

- **Local (Ollama)** — the default, and the only option where nothing leaves your computer. It uses a model you're running yourself.
- **OpenAI-compatible** — OpenAI, OpenRouter, Groq, together.ai, or anything else speaking the same format.
- **Anthropic (Claude)**.

Picking either of the last two means your transaction descriptions and amounts are sent to that company, which is a real privacy trade-off — so the Settings page won't let you save it until you tick a box confirming you understand. The sidebar indicator and the in-app guide always reflect what's actually switched on. Any API key you enter is stored in a local settings file and is never shown back to you in full.

If the model isn't reachable, the app tells you with a warning instead of leaving an upload stuck.

## Questions

**Where is my data kept?** In a single database file at `~/.sg-expenditure-tracker/data.db`. **Settings → Change Database Path** lets you move it — pointing it at a Dropbox or OneDrive folder is an easy way to get backups and access from another computer.

**Does it need my bank login?** No. It only reads statement PDFs you've already downloaded yourself, and never connects to your bank.

**My statement won't upload.** Make sure it's the e-statement PDF downloaded from the bank, not a scan, a photo, or a printed-then-re-saved copy — the app reads the text inside the file, which those versions don't have. Also check the bank is one that reads today — **Settings → Region** lists which banks parse and which are only recognized.

**My browser didn't open.** The small window the app opens shows its address (`http://127.0.0.1:8123` by default) — type that into your browser yourself.

**I want to start over.** Settings has buttons to delete your transactions, rules, or contacts individually, or everything at once.

## A closer look

| Rules — your own categorization logic, top to bottom | Default Rules — the built-in merchant list, read-only |
|---|---|
| ![The Rules page: a drag-to-reorder list of user rules, each with its match text, target category and priority](docs/screenshots/rules.jpg) | ![The Default Rules page: the built-in merchant word bank, grouped by category and read-only](docs/screenshots/default-rules.jpg) |

**Contacts** map a PayNow identifier (phone, UEN, or account number) to a name and a default category, so transfers to people you pay regularly categorize themselves instead of sitting in "needs review":

![The Contacts page: each contact with its linked PayNow identifiers, default category and historical spend](docs/screenshots/contacts.jpg)

## Adding a bank

The goal is to read statements from any Singapore bank; UOB is simply the one there were real statements to build against. DBS and OCBC already have detection in place — the app can tell a DBS statement from an unreadable file — so what's missing for each is the parser itself, which is written against real sample statements. Everything downstream (categorization, refunds, duplicate detection, the dashboard) is bank-agnostic and needs no changes.

If you have statements from a bank you'd like read, that's the blocker worth removing: [open a bank support request](https://github.com/syoopie/spend-track/issues/new?template=bank-support.yml) (don't attach a real statement — it has your account number in it), or see `backend/src/app/parsing/` for how a parser plugs in — each is one folder implementing `detect()` and `parse()`, registered in one list. **Settings → Region** always shows the live state: which banks parse, and which are recognized but waiting on a parser.

## Run it from source

Everything the download does, from a checkout — for anyone who'd rather not run an unsigned binary, is on a platform with no build yet, or wants to change something. Both prerequisites have ordinary installers: **[uv](https://docs.astral.sh/uv/)** (Python) and **[Node.js](https://nodejs.org/)** 18 or newer.

<details>
<summary><b>Start it with one script</b> — the simplest way to run from source</summary>

```bash
git clone https://github.com/syoopie/spend-track.git
cd spend-track
./scripts/start.sh
```

On Windows, double-click `scripts\start.bat` (or run it from a terminal); `scripts/start.ps1` is the PowerShell equivalent the `.bat` calls.

The script installs what's missing, starts the API and the UI, waits for both to come up, and opens `http://localhost:5173`. `Ctrl+C` in that terminal stops both. Re-running it is safe — it notices what's already running instead of starting a second copy.

The first run takes a few minutes while dependencies download; after that it starts in seconds.

</details>

<details>
<summary><b>Run the two servers by hand</b> — for editing code with hot reload</summary>

**Backend** (from `backend/`) — serves the API on `http://127.0.0.1:8000`:

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The SQLite database defaults to `~/.sg-expenditure-tracker/data.db`; `SG_TRACKER_DB_PATH` overrides it, which is handy for pointing a second instance at a scratch database.

**Frontend** (from `frontend/`) — serves the UI on `http://localhost:5173` and proxies `/api/*` to the backend:

```bash
npm install
npm run dev
```

</details>

<details>
<summary><b>Build the download yourself</b> — the same executable CI publishes</summary>

```bash
cd backend
uv run --group build python scripts/build_desktop.py
```

Compiles the frontend, then freezes it and the API into one executable in `backend/dist/` — `SpendTrack.exe` on Windows, `SpendTrack.app` on macOS, `SpendTrack` on Linux.

PyInstaller freezes the interpreter it runs under, so each platform's build has to happen on that platform; `.github/workflows/desktop-build.yml` does all three on every pull request, smoke-starts each one, and attaches them to a release on a `v*` tag.

</details>

## For developers

<details>
<summary><b>Tests</b></summary>

```bash
cd backend && uv run pytest
```

Parser regression tests run against every committed sanitized sample PDF, alongside full API integration tests via FastAPI's `TestClient` — all pass on a fresh clone with no setup beyond `uv sync`. A few extra tests run only if you've dropped your own real UOB statements into a local, gitignored `PDF Examples/UOB/` folder (they cross-validate against each statement's own printed totals) and are skipped, not failed, when it doesn't exist.

The synthetic samples are generated by `backend/scripts/generate_sample_pdfs.py` at the exact column positions the real parser expects, so they exercise the genuine parsing path. `backend/scripts/seed_demo_data.py` rebuilds the exact database the screenshots above were taken from — a throwaway `SG_TRACKER_DB_PATH`, the whole sample folder uploaded in one batch, plus placeholder contacts and rules.

The frontend has no automated test suite yet — verified manually in-browser, with `npx tsc -b` and `npm run build` for type and build checks.

</details>

<details>
<summary><b>Stack</b></summary>

- **Backend**: Python 3.12, FastAPI, SQLite (stdlib `sqlite3`, no ORM), `pdfplumber` for PDF parsing, `pypdf` for encrypted PDFs, `httpx` for AI provider calls. Managed with `uv`.
- **Frontend**: React + TypeScript, Vite, Tailwind CSS v4, TanStack Query, React Router. No charting library — every chart is hand-rolled SVG.
- **Packaging**: PyInstaller. The compiled frontend rides inside the executable and is served by the same FastAPI process as the API (`app/webui.py`), so a packaged copy is one process on one port with no Node anywhere — Node is a build-time dependency only.

</details>

<details>
<summary><b>Project layout</b></summary>

```text
backend/src/app/
  parsing/       per-bank statement parsers (uob/, dbs/, ocbc/) behind a shared registry
  engine/        categorization rules, fingerprinting/dedup, refund pairing, in-memory staging store
  engine/ai_providers/  pluggable AI categorization: Ollama / OpenAI-compatible / Anthropic adapters
  routers/       FastAPI routes, one file per resource
  repo.py        DB-query helpers shared across routers
  errors.py      shared API error-response construction
  migrations.py  schema DDL migration + default-rule/category reconciliation
  webui.py       serves the compiled UI in a packaged build (no-op in dev)
  desktop.py     the entry point behind the double-clickable build
frontend/src/
  api/           fetch client + typed React Query hooks
  pages/         one file per screen
  components/    shared UI (charts, modals, sidebar)
backend/packaging/  PyInstaller spec for the desktop build
docs/            original design docs + screenshots
scripts/         start.bat / start.sh / start.ps1
```

</details>

<details>
<summary><b>Where the reasoning lives</b></summary>

`CLAUDE.md` documents the non-obvious implementation decisions — why PDF parsing clusters whitespace instead of extracting tables, the categorization precedence order, why staging is in-memory, how the default rule bank is reconciled on every startup, what the packaged build has to be told by hand, and the known traps in each area.

`docs/technical-spec.md` and `docs/ux-spec.md` are the original design docs, written before implementation; where the app has since diverged on purpose, that's recorded in `CLAUDE.md` rather than rewritten back into the specs.

`docs/ui-conventions.md` is the living UI checklist — each rule exists because a real instance of it was found and fixed.

</details>
