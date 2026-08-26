# Adding a bank

Everything downstream of a parser — categorization, refund pairing, duplicate
detection, the dashboard — is bank-agnostic. Adding a bank means writing one
folder under `backend/src/app/parsing/` and registering it in one list. This
page covers how, and the part that is actually hard: getting a statement to
build against.

## The hard part first: getting a sample

A parser is written against a real statement, and a real statement carries the
account holder's name, home address, account number and a year of spending.
That is the whole blocker, and it is worth being precise about how blocked it is:

- **No bank publishes a specimen statement.** The banks' own "understanding
  your statement" pages are annotated screenshots, not downloadable PDFs.
- **The template sites that turn up in a search are forgery tools** — they
  sell editable statements for faking proof of income. Don't use them; besides
  the obvious, they are drawn to look right to a human, not to be structured
  like the real thing, which is the only property that matters here.
- **Even mature open-source parsers can't share theirs.**
  [monopoly](https://github.com/benjamin-awd/monopoly), which parses statements
  from 18 institutions, keeps its test statements git-crypt encrypted in its own
  repository. The maintainer of the most complete Singapore parser cannot
  publish a single sample.

So there are exactly three ways to get one, in descending order of usefulness.

### 1. Sanitize your own statement (best)

```
uv run python scripts/sanitize_statement.py ~/Downloads/statement.pdf \
    --redact "YOUR NAME" --redact "ANY OTHER NAME ON IT"
```

This rebuilds the PDF from scratch — it does not draw boxes over your data,
which leaves the data in the file — keeping every word's exact position while
replacing account numbers, references, NRIC/FIN, emails, phone numbers and
transfer counterparties. Identifiers split across words (`4111 1111 1111 1234`)
are handled too.

**It is a two-pass tool, and the second pass is not optional.** No rule can
find a name that nothing introduces — yours in the address block, a joint
holder's, a landlord's, a street. So it writes a `.review.txt` whose first
section lists every name-shaped phrase that survived, with the line each came
from. Read it, re-run with `--redact` for each one, repeat until that list
holds nothing personal. The script's own checks confirm the rules did what
they were asked; they are not a clean bill of health.

Before finishing it re-reads its own output and refuses the file if anything it
removed is still findable anywhere in it — including in the output's *name*,
since `JaneWong-Jan2024.pdf` identifies its owner as well as its contents do.
Pass `--output` to name the result something neutral.

Amounts, dates and merchant names are kept on purpose. They are what a parser
has to read correctly, and the reconciliation checks are written against them.
`--redact-amounts` removes the figures if you'd rather not share them, at the
cost of those checks.

The script's own docstring covers the rest, including `--check-parse`, which
runs the result through this app's parsers.

### 2. Run the parser yourself and report what breaks

Nothing has to leave your machine. Clone, drop your statements into the
gitignored `PDF Examples/<BANK>/` folder, run `uv run pytest`, and report the
failures. Slower to iterate on, but it needs no sanitizing at all.

### 3. Build from the published layout

This is what DBS and OCBC support was built from, and it comes with real
caveats — see below. Only reach for it when nobody has a statement to give.

## Writing the parser

A bank is a package under `parsing/` exposing a `BankParser` subclass with
`detect()` (a cheap anchor-text check) and `parse()`. Register it in
`app/localization.py`'s country profile; `parsing/registry.py` reads that list,
and `GET /api/settings` derives the UI's "which banks work" copy from
`parsing_implemented`, so no user-facing string needs editing.

There are two ways to write the body, and which one is right depends entirely
on whether you have a real statement.

### With a real statement: hand-calibrate, like `parsing/uob/`

Measure the column x-ranges off the statement and write them down as `Column`
definitions. This is what UOB does. It is precise, it copes with layout quirks
that resist generalization, and it is only possible because the numbers came
from a real file.

### Without one: a spec over `parsing/columnar.py`, like `parsing/dbs/`

DBS and OCBC are declarative `TableSpec`s: which columns exist, what words head
them, which rows are furniture rather than transactions, how the statement
prints its own date. Two things make that safe enough to ship:

- **Columns are derived at parse time** from the header row's word positions
  (`pdf_utils.columns_from_header`), so no x-coordinate is hardcoded that
  nobody measured. Each column runs from its own header word's left edge to the
  next one's — not the midpoint of the gap, which starves a wide left-aligned
  description column sitting beside a right-aligned amount column and reads the
  description's tail as money.
- **Every parse ends in a reconciliation check** against a figure the statement
  prints for itself (a `Total` row, a closing balance), and refuses the import
  when they disagree. A parser built without a real sample is exactly the one
  that should not quietly return a wrong balance.

What this approach cannot do is prove the layout is what the bank actually
prints. The fixtures in `PDF Examples (Sanitized)/{DBS,OCBC}/` were drawn from
the same understanding of the layout the parsers were written from, so fixture
and parser are wrong together if that understanding is wrong. **A sanitized
real statement is what upgrades one of these from plausible to verified** — if
you have one, that is the single most useful contribution available.

## Fixtures and tests

Committed fixtures live in `PDF Examples (Sanitized)/<BANK>/`, generated by
`scripts/generate_sample_pdfs.py` (UOB) and `scripts/generate_dbs_ocbc_samples.py`
(DBS, OCBC). They are drawn at the real column positions, so they round-trip
through the real parser rather than being lookalikes.

`PDF Examples/` is a gitignored folder for your own real statements. Tests that
use it discover files by glob and skip when it's absent, so a fresh clone runs
green with no setup.

Each bank's test module should pin specific values for a couple of statements
and then parameterize over *whatever is in the folder*, so a fixture added later
is covered the day it lands.

## A new country

A second `CountryProfile` in `app/localization.py` — currency, transfer scheme,
contact-identifier hint, and which parsers belong to it — plus a starting
merchant word bank in `engine/default_rules.py`. Not a rewrite; the Singapore
profile is simply the one that exists.
