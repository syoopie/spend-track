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
uv run python scripts/sanitize_statement.py ~/Downloads/statement.pdf --check-parse
```

It keeps your statement's geometry, its figures and dates, and your bank's own
wording — the bank name, the column headings, the `BALANCE B/F` and `Total`
rows, the statement date — and replaces every other word with its shape
(`FAIRPRICE FINEST` becomes `XXXXXXXXX XXXXXX`).

That is default-deny: a word is kept only if it is positively recognized, so
anything nobody anticipated is replaced rather than published. It needs no
`--redact` arguments and leaves you no judgement calls, and its verification is
exhaustive rather than heuristic — every word in a finished file must be
template, a date, a figure, or something the script itself wrote.

It costs a parser author nothing, which is measured rather than assumed: a
parser keys on the statement's template and works out columns from geometry,
and never reads a description for anything except passing it through.
Sanitizing every committed fixture leaves all three parsers returning identical
dates, amounts and balances. (Geometry *alone* is not enough, though — strip
the bank's wording too and no parser can even tell which bank it is looking at.)

Three flags matter:

- `--check-parse` runs the result through this app's parsers. If it doesn't
  parse, the script didn't recognize one of your bank's headings — pass
  `--keep "THAT HEADING"`. A loud failure, never a silent leak.
- `--redact "TEXT"` covers the one case default-deny can't: a name that *is* a
  banking word — someone called May, a merchant called Trust. The review file
  it writes lists what was kept verbatim, so you can spot exactly that.
- `--output` renames the result. The file name travels with the file, and
  `JaneWong-Jan2024.pdf` identifies its owner as well as its contents do; the
  script refuses to finish if the output name contains something you redacted.

What it does **not** hide is the figures. Amounts and balances survive, because
they are what a parser has to read correctly and what its reconciliation checks
are written against — the output shows what you spent, just not who you are or
who you paid. `--redact-amounts` replaces them too, at the cost of those checks.

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

## Contributing merchant rules — no statement required

The merchant rule bank in `engine/default_rules.py` is a separate contribution
from a statement sample, and neither blocks the other. It is a list of merchant
strings and the category each belongs to:

```python
"Food & Drink": [
    ("KOPITIAM", "Kopitiam"),
    ("FOUR LEAVES", "Four Leaves"),
],
```

The first element is matched against a transaction's description; the second is
the tidy name shown in the UI. Entries are reconciled into the `rules` table on
every startup, so adding one reaches every existing database with no migration.

**This needs no PDF and no sanitizing.** Send the merchant strings as they
appear on your statement, with the category each belongs to — nothing else
about the statement is relevant, and no sample has to exist for the rules to be
useful.

The in-app entry point is **Default Rules → Suggest a merchant**, since that
page is the list of everything already covered and therefore where a gap gets
noticed; it links straight to
[the merchant-rules issue template](https://github.com/syoopie/spend-track/issues/new?template=merchant-rules.yml).
Anything sitting in **Others** on the dashboard is a merchant no rule matched,
and the grey line under a transaction's tidy name is the raw text a rule would
have to match — trim the reference numbers and terminal IDs around it before
pasting.

The reverse holds too, which is what makes the sanitizer viable: a parser reads
the bank's template and works out columns from geometry, and never reads a
description for anything except passing it through. So a shared statement can
discard every description without costing a parser author anything, and the
rule bank loses nothing by never seeing a statement.

## A new country

A second `CountryProfile` in `app/localization.py` — currency, transfer scheme,
contact-identifier hint, and which parsers belong to it. Not a rewrite; the
Singapore profile is simply the one that exists. Its merchant rules are the
separate contribution above.
