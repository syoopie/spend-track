<div align="center">

<img src="docs/logo.svg" width="72" height="72" alt="">

# SpendTrack

**Turn bank statement PDFs into a spending dashboard — on your own computer, with nothing sent anywhere.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![Runs locally](https://img.shields.io/badge/data-100%25%20local-brightgreen?style=flat-square)](#your-data-stays-on-your-computer)
[![Download](https://img.shields.io/github/v/release/syoopie/spend-track?style=flat-square&label=download&color=e35fd0)](https://github.com/syoopie/spend-track/releases/latest)
[![Python 3.12](https://img.shields.io/badge/python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](backend/pyproject.toml)
[![React 19](https://img.shields.io/badge/react-19-61dafb?style=flat-square&logo=react&logoColor=white)](frontend/package.json)

<sub>**A bank becomes supported the moment there's a statement to build a parser against — that's the whole blocker.** Reads today: **UOB**, **DBS**/**POSB**, **OCBC**. Yours not listed? [Say what you have](https://github.com/syoopie/spend-track/issues/new?template=bank-support.yml) — and never attach a real statement. **Help add your bank**, at the bottom of the app's sidebar, turns one into a shareable sample that keeps the layout and drops your name, account number and references, without leaving your computer.</sub>

</div>

Give it a statement PDF from your bank. It reads every transaction, sorts them into categories, cancels refunds against the purchases they reverse, and shows you where your money went.

**Using it** · [Download and run](#download-and-run) · [Try the sample data](#try-it-before-using-your-own-statements) · [The everyday routine](#the-everyday-routine) · [AI categorization](#optional-let-ai-sort-out-the-leftovers) · [Questions](#questions)

**Working on it** · [Adding a bank](#adding-a-bank) · [Run it from source](#run-it-from-source) · [For developers](#for-developers)

![The dashboard: inflow, outflow and net expenditure for the selected months, a cash flow chart, a category breakdown donut, and the searchable transaction feed](docs/screenshots/dashboard.jpg)

## Your data stays on your computer

No account, no login, nothing uploaded. Your transactions live in one file on your own disk. The app reads PDFs you already have and never contacts your bank. The one exception is the optional AI feature below, off until you switch it on.

## What it does

- **Reads statement PDFs** — bank and credit card, password-protected included. Drop in one or a year's worth at once. UOB, DBS/POSB and OCBC parse today; any other bank is [one parser away](#adding-a-bank). An unrecognized file says so instead of guessing.
- **Categorizes automatically** from rules you can see and edit, plus a built-in merchant list. Your own rules win.
- **Shows you everything before it's saved.** Each upload lands in a review screen, with anything uncertain flagged for you to decide.
- **Doesn't double-count.** The same statement uploaded twice is skipped. A card bill paid from a linked account isn't counted on top of the purchases.
- **Nets off refunds** against the purchase they reverse, matching merchant and amount so unrelated transactions aren't paired.
- **Names who you pay.** Save a PayNow number or UEN once; later transfers to them label and categorize themselves.
- **Charts the picture** — money in and out, spending by category, month-on-month pace, top merchants, most-paid contacts. All filterable by date and account.
- **Exports in one click.** **Settings → Download Backup** gives a zip that opens in any SQLite browser.

## Download and run

No installers, no accounts, no command line. Grab the file for your computer from the [latest release](https://github.com/syoopie/spend-track/releases/latest), open it, and the app appears in your browser.

| Your computer | Download | How to open it |
|---|---|---|
| **Windows** | `SpendTrack-windows-x86_64.exe` | Double-click it. Windows will warn that the publisher is unknown — click **More info** → **Run anyway**. |
| **Mac** (Apple silicon) | `SpendTrack-macos-arm64.zip` | Unzip, then **right-click** the app → **Open** → **Open**. Double-clicking the first time gives a "cannot be opened" message; right-click → Open is what gets past it. |
| **Mac** (Intel) | `SpendTrack-macos-x86_64.zip` | Same as above. Not sure which Mac you have? Apple menu → **About This Mac**: "Apple M1/M2/…" means Apple silicon, "Intel" means this one. |
| **Linux** | `SpendTrack-linux-x86_64` | `chmod +x SpendTrack-linux-x86_64` once, then run it. |

A small window opens showing where your data is stored and the address the app is running at, and your browser opens on the dashboard. **Closing that window closes the app.** Your data is saved as you go.

<details>
<summary>Why does my computer warn me about it?</summary>

Both warnings mean the same thing: the download isn't signed with a paid developer certificate (Apple charges $99/year, Microsoft rather more). Nothing about the app changes if you get past the warning — but you shouldn't take that on faith from the person who wrote it. Everything here is source code you can read, and the download is built in the open by [this GitHub Actions workflow](.github/workflows/desktop-build.yml), from the exact commit each release names. If you'd rather not run an unsigned binary at all, [run it from source](#run-it-from-source) instead.

</details>

### Try it before using your own statements

You don't need real statements to look around. `PDF Examples (Sanitized)/` holds a fictional customer's — a year of UOB account and card statements plus smaller DBS and OCBC sets, ~300 transactions, the same data behind every screenshot here. Two of the DBS files are real statements run through the sanitizer, so a live layout is in the mix. Select the folder, upload it in one go, and **Settings** clears it out afterwards.

### The everyday routine

1. **Upload** one or more statement PDFs (button in the sidebar, or drag them onto the window).
2. **Review** how each transaction was categorized, and fix anything that looks off.
3. **Commit** — the transactions join your history.
4. **Explore** the dashboard, filtered by whatever date range and account you care about.

The app has a built-in **User Guide** in the sidebar that walks through each screen in more detail.

## Optional: let AI sort out the leftovers

**Off by default.** Turn it on under **Settings** and the transactions the rules couldn't place get sent to an AI model, which suggests a category, a tidy merchant name, and a rule to save. The suggestions land pre-filled in the review screen for you to accept, edit, or reject — nothing is applied on its own. Close the review screen and they wait for you. An unreachable model shows a warning instead of hanging the upload; a slow pass gets a **Terminate** button after 15 seconds.

Three model choices:

- **Local (Ollama)** — the default, and the only one where nothing leaves your computer.
- **OpenAI-compatible** — OpenAI, OpenRouter, Groq, together.ai, anything speaking that format.
- **Anthropic (Claude)**.

The last two send your descriptions and amounts to that company. Settings won't save either until you tick a box confirming you understand, and any API key you enter is kept in a local file and never shown back in full.

## Questions

**How do I back up or move my data?** **Settings → Download Backup** gives a `.zip` with your database, settings, and a note on restoring. On the other computer, start the app once to create its folder, quit, and copy the two files in. Your AI key is left out on purpose — re-enter it after restoring.

**Where is my data kept?** One SQLite file at `~/.spendtrack/data.db`; **Settings** shows the path. **Settings → Change Database Path** moves it — point it at a Dropbox or OneDrive folder for continuous backups. (An install from before the rename keeps its old `~/.sg-expenditure-tracker` folder.)

**Does it need my bank login?** No. It reads statement PDFs you downloaded yourself and never connects to your bank.

**My statement won't upload.** Use the e-statement PDF from the bank, not a scan or a photo — the app reads the text inside the file. Check the bank parses today under **Settings → Region**. A "did not reconcile" message is the parser refusing figures it can't check against the statement's own totals; [please report it](https://github.com/syoopie/spend-track/issues/new?template=bank-support.yml).

**My browser didn't open.** The app window shows its address (`http://127.0.0.1:8123` by default) — open that yourself.

**I want to start over.** Settings deletes your transactions, rules, or contacts, individually or all at once.

## A closer look

| Rules — your own categorization logic, top to bottom | Default Rules — the built-in merchant list, read-only |
|---|---|
| ![The Rules page: a drag-to-reorder list of user rules, each with its match text, target category and priority](docs/screenshots/rules.jpg) | ![The Default Rules page: the built-in merchant word bank, grouped by category and read-only](docs/screenshots/default-rules.jpg) |

**Contacts** map a PayNow identifier (phone, UEN, or account number) to a name and a default category, so transfers to people you pay regularly categorize themselves instead of sitting in "needs review":

![The Contacts page: each contact with its linked PayNow identifiers, default category and historical spend](docs/screenshots/contacts.jpg)

## Adding a bank

The goal is to read statements from any bank, anywhere. Everything downstream of a parser — categorization, refunds, duplicate detection, the dashboard — is bank-agnostic, so a new bank is one folder under `backend/src/app/parsing/` implementing `detect()` and `parse()`, registered in one list. **Settings → Region** always shows the live state.

The hard part is never the code. A parser is written against a real statement, and a real statement carries your name, address, account number and a year of spending — which is why nobody can simply send one. No bank publishes a specimen, the "statement template" sites a search turns up are forgery tools, and even [monopoly](https://github.com/benjamin-awd/monopoly), the most complete open-source Singapore parser, keeps its own test statements encrypted in its repository.

**So the app has a page for it: Help add your bank**, at the bottom of the sidebar. Pick your statement and it rebuilds it into a shareable one — rebuilds, rather than drawing boxes over it, since a box leaves the text underneath. Then it shows you the result before you do anything with it: a preview of the whole file, the list of words it kept, and a click to remove any of them. You get a download and a link to the issue form; nothing is uploaded, and you attach the file yourself.

It keeps the layout, the figures, the dates and your bank's own wording — the headings, the `BALANCE B/F` and `Total` rows — and replaces every other word with its shape. Default-deny, so it needs no decisions from you: anything it doesn't positively recognize is replaced rather than published. And it costs a parser nothing, because a parser reads the statement's template and its geometry, never the descriptions.

From a clone, `scripts/sanitize_statement.py` is the same thing on the command line:

```
uv run python scripts/sanitize_statement.py statement.pdf --check-parse
```

That's the contribution worth making: [open a bank support request](https://github.com/syoopie/spend-track/issues/new?template=bank-support.yml) and attach a sanitized sample — or just run the parsers against your own files locally and report what breaks, which needs no sanitizing at all. **[docs/adding-a-bank.md](docs/adding-a-bank.md)** has the details, including how DBS and OCBC were built from their published layouts when no statement was available, and why those parsers refuse to import figures that don't reconcile.

**Merchant rules are a separate contribution, and need no statement at all.** The built-in word bank in `engine/default_rules.py` is just merchant strings and the category each belongs to — send yours and they reach every install on the next release. A parser never reads a description, so the two contributions are independent in both directions: rules need no sample, and a shared sample can drop every description without costing a parser anything. The app has a button for it: **Default Rules → Suggest a merchant**, which is the page where you'd notice something is missing in the first place. Or [open a merchant-rules issue](https://github.com/syoopie/spend-track/issues/new?template=merchant-rules.yml) directly.

A new **country** is a second `CountryProfile` in `backend/src/app/localization.py` — currency, transfer scheme, the contact-identifier hint, and which parsers belong to it. Not a rewrite; the Singapore profile is just the one that exists.

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

The SQLite database defaults to `~/.spendtrack/data.db`; `SPENDTRACK_DB_PATH` overrides it, which is handy for pointing a second instance at a scratch database. (The pre-rename `SG_TRACKER_*` variable names still work — see `backend/src/app/config.py`.) `./scripts/start-test.sh` (or `.ps1` on Windows) automates exactly that: a whole second instance on ports 8001/5174 against a scratch database at `.scratch-test/data.db`, so you (or an agent) can try something without touching your real data or the copy already running on 5173/8000.

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

PyInstaller freezes the interpreter it runs under, so each platform's build has to happen on that platform; `.github/workflows/desktop-build.yml` does all three, smoke-starts each one, and attaches them to a release. It runs on a `v*` tag or on demand from the Actions tab (where naming a tag publishes a release), not on every pull request.

</details>

## For developers

<details>
<summary><b>Tests</b></summary>

```bash
cd backend && uv run pytest
```

Parser regression tests run against every committed sanitized sample PDF, alongside full API integration tests via FastAPI's `TestClient` — all pass on a fresh clone with no setup beyond `uv sync`. A few extra tests run only if you've dropped your own real statements into a local, gitignored `PDF Examples/<BANK>/` folder (they cross-validate against each statement's own printed totals) and are skipped, not failed, when it doesn't exist.

The synthetic samples are generated by `backend/scripts/generate_sample_pdfs.py` at the exact column positions the real parser expects, so they exercise the genuine parsing path. `backend/scripts/seed_demo_data.py` rebuilds the exact database the screenshots above were taken from — a throwaway `SPENDTRACK_DB_PATH`, the whole sample folder uploaded in one batch, plus placeholder contacts and rules.

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
