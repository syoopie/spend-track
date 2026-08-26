"""Turn a real bank statement into one that can be shared with developers.

Why this exists
---------------
Every parser in this project needs a real statement to be built against, and
nobody can hand one over: it carries a name, a home address, an account number
and a year of spending. UOB got parsed because the author had UOB statements;
DBS and OCBC had to be written against their published layouts instead (see
`app/parsing/columnar.py`). This closes that gap.

What it keeps, and why that is all a parser needs
-------------------------------------------------
It keeps the statement's *geometry* and the *bank's own wording*, and replaces
everything else with its shape:

    FAST Payment / Receipt PayNow    ->  XXXX Xxxxxxx / Xxxxxxx XxXxx
    Transfer To: TAN WEI MING            Xxxxxxxx Xx: XXX XXX XXXX
    01 Feb   BALANCE B/F  5,000.00   ->  01 Feb   BALANCE B/F  5,000.00

That is enough because a parser never reads a transaction description. It keys
on the bank name, the column headings, the BALANCE B/F and Total rows and the
statement date - all of which are printed identically on every statement the
bank issues and belong to nobody - then uses each word's position to work out
which column it is in. Replacing every description across this project's whole
fixture set leaves all three parsers returning identical dates, amounts and
balances, which `test_structure_only_costs_the_parsers_nothing` pins.

Geometry alone is not enough, though: strip the bank's wording too and no
parser can even tell which bank it is looking at.

So the rule is default-deny. A word is kept only if it is positively
recognized as template, a date, or a figure; anything else - anything nobody
anticipated - is replaced rather than published. That means no judgement calls
for you, and no list of maybe-personal words to review.

What it does not protect
------------------------
The figures. Amounts and balances survive, because they are what a parser has
to read correctly and what its reconciliation checks are written against. The
output still shows what you spent, just not who you are or who you paid.
--redact-amounts replaces them too, at the cost of those checks.

How it works, and why not a black box
-------------------------------------
Drawing a black rectangle over text in a PDF does not remove the text. It is
still in the content stream, still selectable, still there for anyone who runs
`pdftotext`. Redaction tools that get this wrong have leaked real documents.

So this does not edit your PDF. It reads the position and content of every
word and draws a *new* PDF containing only the surviving ones. The original
text, images, annotations, attachments, metadata and any earlier revision left
in the file do not exist in the output, because the output was built empty.

Using it
--------
    uv run python scripts/sanitize_statement.py statement.pdf --check-parse

If the result does not parse, this script did not recognize one of your bank's
headings - pass `--keep "THAT HEADING"` and try again. That failure is loud;
it is never a silent leak.

Before finishing it re-reads its own output and refuses the file unless every
surviving word is one it can account for - including the output's *name*,
since "JaneWong-Jan2024.pdf" identifies its owner as well as its contents do.
Use --output to name the result something neutral.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import pdfplumber
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

# --------------------------------------------------------------------------
# What is kept
# --------------------------------------------------------------------------

#: An amount. The three alternatives are deliberately not "any run of digits":
#: a figure qualifies by being comma-grouped, by having decimals, or by being
#: short enough not to identify anything. A bare "123456" matches none of them
#: and is treated as an account number, which is the safe way round.
MONEY_RE = re.compile(
    r"^\(?-?\$?(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{1,2}|\d{1,3})\)?\s*(?:CR|DR)?$",
    re.I,
)
#: A date in the shapes statements print: "01", "15/03", "15-03-2024".
DATE_RE = re.compile(r"^(\d{1,2}[-/.]\d{1,2}(?:[-/.]\d{2,4})?|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2})$")

#: The statement template's own vocabulary: bank names, table headings, the
#: furniture rows, month names, currency and polarity markers. Everything a
#: parser keys on lives here, and none of it belongs to the customer - it is
#: printed identically on every statement the bank issues.
#:
#: Being generous is safe: no customer's name is in this list, and the cost of
#: a miss is only that the sample needs a --keep to parse, which --check-parse
#: surfaces immediately.
CHROME_VOCABULARY = frozenset(
    """
    bank banking corporation limited ltd pte berhad group
    united overseas uob dbs posb oversea-chinese ocbc citibank hsbc maybank
    standard chartered trust gxs anext
    statement statements account accounts current savings cheque deposit deposits
    withdrawal withdrawals balance balances credit debit card cards
    transaction transactions details detail description descriptions
    date dates period from to as at value posting post trans effective
    total totals subtotal sub grand previous new opening closing
    brought carried forward b/f c/f bf cf
    minimum payment due paid amount amounts limit available outstanding
    currency singapore dollar sgd usd myr eur gbp cr dr db
    jan feb mar apr may jun jul aug sep sept oct nov dec
    january february march april june july august september october november december
    page pages continued cont summary overview no number ref reference
    interest charges fee fees gst rate
    """.split()
) | frozenset(
    # Connectives, which carry nothing and appear inside anchors a parser
    # matches whole: UOB looks for the literal "Statement of Account", so
    # dropping "of" makes the sample unrecognizable.
    "a an and at as by for from in of on or the this to with your".split()
)


@dataclass(frozen=True)
class Word:
    """One word, with the geometry a parser cares about."""

    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    size: float
    bold: bool


def _pseudonym_digits(original: str) -> str:
    """A stable stand-in for a number: same shape, same length.

    Hashed on the digits alone, not the separators, so "4111-1111-1111-1234"
    and "4111111111111234" land on the same placeholder - a statement is free
    to group one number differently in two places, and a parser grouping by
    account must still see one account. Not reversible: the hash is truncated
    to one digit per character, and nothing is written to disk.
    """
    digest = hashlib.sha256("".join(c for c in original if c.isdigit()).encode()).hexdigest()
    out = []
    cursor = 0
    for char in original:
        if char.isdigit():
            out.append(str(int(digest[cursor % len(digest)], 16) % 10))
            cursor += 1
        else:
            out.append(char)  # keep separators, so "123-456789-0" stays that shape
    return "".join(out)


def _shape_of(original: str) -> str:
    """X for a capital, x for a lower-case letter, everything else untouched.

    Digits must be pseudonymised *before* this, not after: shaping alone maps
    only letters, so a reference like "PIB0000123456789012" would come out as
    "XXX0000123456789012" - the whole thing intact behind a masked prefix.
    """
    return "".join("X" if c.isupper() else "x" if c.isalpha() else c for c in original)


def is_chrome(text: str) -> bool:
    """Is this word part of the bank's template rather than the customer's data?

    Matched twice: with punctuation stripped from the ends ("Balance:"), and
    with every non-alphanumeric removed, because banks punctuate inside their
    own headings too - UOB prints "Credit Card(s) Statement", and only the
    second form reduces "Card(s)" to the "cards" in the vocabulary.
    """
    lowered = text.lower()
    if lowered.strip("(),.:;/-") in CHROME_VOCABULARY:
        return True
    return "".join(c for c in lowered if c.isalnum()) in CHROME_VOCABULARY


def is_money(text: str) -> bool:
    return bool(MONEY_RE.match(text)) and any(c.isdigit() for c in text)


def is_date(text: str) -> bool:
    return bool(DATE_RE.match(text))


def is_year(text: str) -> bool:
    """A bare four-digit year, as in "Statement Date 20 FEB 2024".

    Needs its own check because DATE_RE only matches one- and two-digit day
    numbers and fully-punctuated dates, so a lone "2024" reads as neither a
    date nor an amount - and every digit-bearing word is otherwise replaced
    regardless of length, which put every statement's year through the
    pseudonymiser and moved all its transactions to the year 6557. Bounded to
    a plausible range so a four-digit card group still goes.
    """
    return len(text) == 4 and text.isdigit() and 1900 <= int(text) <= 2099


def keeps(text: str, keep: frozenset[str]) -> bool:
    """Everything this script is willing to leave in the output verbatim."""
    return is_chrome(text) or is_year(text) or is_date(text) or text.lower() in keep


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


def group_lines(words: list[Word], y_tol: float = 3.0) -> list[list[Word]]:
    """Cluster words into physical lines, the way the parsers do.

    Only the rebuild needs this - word spacing has to be reproduced between
    words that sit side by side - but it is the parsers' own rule, so keeping
    it identical means the output re-reads as the same rows.
    """
    lines: list[list[Word]] = []
    current: list[Word] = []
    anchor: float | None = None
    for word in sorted(words, key=lambda w: (w.top, w.x0)):
        if anchor is None or abs(word.top - anchor) <= y_tol:
            current.append(word)
            anchor = word.top if anchor is None else anchor
        else:
            lines.append(sorted(current, key=lambda w: w.x0))
            current = [word]
            anchor = word.top
    if current:
        lines.append(sorted(current, key=lambda w: w.x0))
    return lines


def _normalize(text: str) -> str:
    return re.sub(r"[^\w]", "", text).lower()


def _literal_matches(words: list[Word], literals: list[str]) -> set[int]:
    """Indices of the words covered by a --redact value.

    Matched against whole words joined end to end, never as a substring, and
    with punctuation stripped from both sides. That means you do not have to
    guess how the PDF split your name: "Anne-Marie" typed once matches whether
    the statement prints it as one word, as "Anne Marie", or hyphenated.
    """
    normalized = [_normalize(w.text) for w in words]
    hits: set[int] = set()
    for literal in literals:
        target = _normalize(literal)
        if not target:
            continue
        for start in range(len(normalized)):
            joined = ""
            for end in range(start, len(normalized)):
                joined += normalized[end]
                if len(joined) > len(target):
                    break
                if joined == target:
                    hits.update(range(start, end + 1))
                    break
    return hits


def redact_line(
    words: list[Word],
    literals: list[str] = (),
    keep: frozenset[str] = frozenset(),
    redact_amounts: bool = False,
    written: set[str] | None = None,
) -> list[Word]:
    """Replace every word that isn't template, a date or a figure.

    --redact is still worth having even under default-deny, for the one case
    the vocabulary cannot cover: a name that *is* a template word. Somebody
    called May, or a merchant called Trust, is kept by is_chrome and has to be
    named explicitly.
    """
    literal_hits = _literal_matches(words, list(literals))
    out: list[Word] = []

    for index, word in enumerate(words):
        text = word.text

        if index not in literal_hits:
            if is_money(text):
                out.append(replace(word, text=re.sub(r"\d", "0", text)) if redact_amounts else word)
                continue
            if keeps(text, keep) or not any(c.isalnum() for c in text):
                out.append(word)
                continue

        replacement = _shape_of(_pseudonym_digits(text))
        if written is not None:
            written.add(replacement)
        out.append(replace(word, text=replacement))

    return out


# --------------------------------------------------------------------------
# Reading and rebuilding
# --------------------------------------------------------------------------


def read_pages(path: Path, password: str | None):
    """Every page as (width, height, words, dropped), decrypting in memory."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from app.parsing.pdf_io import EncryptedPdfError, IncorrectPasswordError, open_pdf

    try:
        pdf = open_pdf(path.read_bytes(), password)
    except EncryptedPdfError:
        raise SystemExit(
            f"{path.name} is password-protected. Re-run with --password (it is used only "
            "to decrypt in memory and is never written anywhere)."
        ) from None
    except IncorrectPasswordError:
        raise SystemExit(f"The password given does not decrypt {path.name}.") from None

    pages = []
    with pdf:
        for page in pdf.pages:
            words, rotated = [], 0
            extracted = page.extract_words(
                use_text_flow=False, keep_blank_chars=False, extra_attrs=["size", "fontname", "upright"]
            )
            for w in extracted:
                if not w.get("upright", True):
                    # Vertical text is a sidebar or a watermark, never a
                    # transaction, and reproducing rotated geometry faithfully
                    # is more trouble than it is worth. Dropping is safe.
                    rotated += 1
                    continue
                words.append(
                    Word(
                        text=w["text"],
                        x0=float(w["x0"]),
                        x1=float(w["x1"]),
                        top=float(w["top"]),
                        bottom=float(w["bottom"]),
                        size=float(w.get("size") or 9.0),
                        bold="bold" in str(w.get("fontname", "")).lower(),
                    )
                )
            pages.append((float(page.width), float(page.height), words, rotated))
    return pages


def write_pdf(out_path: Path, pages, notice: str) -> None:
    """Draw a fresh PDF containing the surviving words and nothing else."""
    c = canvas.Canvas(str(out_path))
    c.setTitle("Sanitized bank statement sample")
    c.setAuthor("sanitize_statement.py")
    c.setSubject(notice)
    c.setCreator("spendtrack sanitize_statement.py")

    for width, height, lines, _dropped in pages:
        c.setPageSize((width, height))
        for line in lines:
            for index, word in enumerate(line):
                if not word.text.strip():
                    continue
                font = "Helvetica-Bold" if word.bold else "Helvetica"
                size = max(word.size, 1.0)
                # pdfplumber measures `bottom` from the top of the page;
                # reportlab measures y from the bottom, and draws from the
                # baseline, which sits a descender above the box's lower edge.
                y = height - word.bottom + size * 0.21
                _draw_fitted(c, word.text, font, size, word.x0, word.x1, y)

                # Then a space glyph spanning the gap to the next word.
                #
                # Without it the output re-reads as one run-on word per line.
                # pdfplumber splits a line into words at whitespace characters
                # first, falling back to a gap-width threshold (3pt) only
                # otherwise - and inter-word gaps on a real statement are
                # routinely under 3pt, because the source PDF had an actual
                # space character doing the splitting. Drawing each word on its
                # own removes those, so they have to be put back, or every
                # parser here (all of which go through extract_words) sees one
                # giant token per line.
                if index + 1 < len(line):
                    gap_start, gap_end = word.x1, line[index + 1].x0
                    if gap_end > gap_start:
                        _draw_fitted(c, " ", font, size, gap_start, gap_end, y)
        c.showPage()
    c.save()


def _draw_fitted(c: canvas.Canvas, text: str, font: str, size: float, x0: float, x1: float, y: float) -> None:
    """Draw `text` so it occupies exactly the box [x0, x1].

    Horizontally scaled to fit, because the geometry is the point: the parsers
    bucket words into columns by x0 and x1, so a replacement rendering wider or
    narrower would move a word into the next column. Slightly condensed glyphs
    are a cost worth paying.
    """
    c.setFont(font, size)
    target = x1 - x0
    natural = stringWidth(text, font, size)
    if target > 0 and natural > 0:
        c.saveState()
        c.translate(x0, y)
        c.scale(target / natural, 1.0)
        c.drawString(0, 0, text)
        c.restoreState()
    else:
        c.drawString(x0, y, text)


# --------------------------------------------------------------------------
# Checking the result
# --------------------------------------------------------------------------


def survivors(out_path: Path, keep: frozenset[str], written: set[str]) -> list[str]:
    """Words in the output this script cannot account for.

    Default-deny makes verification exhaustive rather than heuristic: every
    word in a finished file must be template, a date, a figure, something the
    contributor asked to keep, or text this script itself wrote. Anything else
    slipped through, and there is no need to guess whether it looks personal -
    it should not be there at all.

    `written` is needed because a replaced *number* is indistinguishable by
    inspection from one that survived: both are digit strings, and the whole
    point of the check is to catch the rule having failed to fire. Replaced
    words are still looked for in the finished file rather than assumed
    present, so this stays a check on the artifact and not on the model.
    """
    with pdfplumber.open(out_path) as pdf:
        tokens = [w["text"] for page in pdf.pages for w in page.extract_words()]
    return sorted(
        {
            token
            for token in tokens
            if any(c.isalnum() for c in token)
            and token not in written
            and not is_money(token)
            and not keeps(token, keep)
        }
    )


def verify(out_path: Path, keep: frozenset[str], literals: list[str], output_name: str, written: set[str]) -> list[str]:
    """Re-read the finished file the way a recipient would."""
    problems = [
        f"a word survived that is not template, a date or a figure: {word}"
        for word in survivors(out_path, keep, written)
    ]

    with pdfplumber.open(out_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages).lower()
    for literal in literals:
        if literal.strip() and literal.lower() in text:
            problems.append(f'the text you asked to remove is still present: "{literal}"')

    # The file name travels with the file, and is what gets attached to an
    # issue. Checked against the *output* name, since passing --output is the
    # fix and reading the input's name would refuse to accept it.
    for literal in literals:
        for part in literal.split():
            if len(part) >= 3 and part.lower() in output_name.lower():
                problems.append(f'the output file name "{output_name}" contains "{part}" - pass --output to rename it')
    return problems


def write_review(path: Path, pages, written: set[str], source_name: str) -> list[str]:
    """List the words kept verbatim, so a human can confirm none is personal.

    Short by construction - it is the template vocabulary that appeared in this
    statement, tens of words rather than hundreds - because everything else was
    replaced rather than judged.
    """
    kept = sorted(
        {
            word.text
            for _w, _h, lines, _d in pages
            for line in lines
            for word in line
            if any(c.isalpha() for c in word.text) and word.text not in written
        }
    )
    path.write_text(
        "\n".join(
            [
                f"Words kept verbatim from {source_name}",
                "",
                "Everything else was replaced with its shape. These survived because",
                "this script recognizes them as your bank's own template wording, which",
                "is what a parser reads. Skim it: if your name or your street happens to",
                "be a banking word (someone called May, a merchant called Trust), it is",
                "in here, and --redact removes it.",
                "",
                "Amounts and balances were kept too, and are not listed. They are what a",
                "parser has to read correctly. Use --redact-amounts to replace them.",
                "",
                f"--- {len(kept)} words ---",
                *kept,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return kept


def check_parse(out_path: Path) -> str:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from app.parsing.base import UnparseableStatementError
    from app.parsing.registry import detect_and_parse

    try:
        with pdfplumber.open(out_path) as pdf:
            statement = detect_and_parse(pdf.pages)
    except UnparseableStatementError as exc:
        return f"does not parse yet: {exc}"
    except Exception as exc:  # a parser bug is exactly what a new sample exposes
        return f"parser raised {type(exc).__name__}: {exc}"
    counts = ", ".join(f"{a.account_type} ({len(a.transactions)} transactions)" for a in statement.accounts)
    return f"parses as {statement.bank_name}: {counts}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip personal data from a bank statement PDF, keeping the layout a parser needs.",
    )
    parser.add_argument("pdf", type=Path, help="the statement to sanitize")
    parser.add_argument("-o", "--output", type=Path, help="output path (default: <name>.sanitized.pdf)")
    parser.add_argument("--password", help="password, if the statement is protected (never stored)")
    parser.add_argument(
        "--keep",
        action="append",
        default=[],
        metavar="TEXT",
        help="wording to preserve that this script doesn't recognize as your bank's template. "
        "Reach for it when --check-parse says the result doesn't parse. Repeatable.",
    )
    parser.add_argument(
        "--redact",
        action="append",
        default=[],
        metavar="TEXT",
        help="text to remove even though it looks like template - a person called May, "
        "a merchant called Trust. Repeatable.",
    )
    parser.add_argument(
        "--redact-amounts",
        action="store_true",
        help="replace the figures too. Shares the structure only, and defeats the reconciliation "
        "checks a parser is tested against - prefer leaving it off.",
    )
    parser.add_argument("--check-parse", action="store_true", help="try parsing the result with this app's parsers")
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        raise SystemExit(f"No such file: {args.pdf}")

    out_path = args.output or args.pdf.with_name(args.pdf.stem + ".sanitized.pdf")
    review_path = out_path.with_suffix(".review.txt")
    keep = frozenset(word.lower() for phrase in args.keep for word in phrase.split())

    pages = read_pages(args.pdf, args.password)
    written: set[str] = set()
    sanitized = [
        (
            width,
            height,
            [redact_line(line, args.redact, keep, args.redact_amounts, written) for line in group_lines(words)],
            dropped,
        )
        for width, height, words, dropped in pages
    ]

    write_pdf(out_path, sanitized, "Sanitized sample - see scripts/sanitize_statement.py")
    kept = write_review(review_path, sanitized, written, args.pdf.name)

    print(f"Wrote {out_path}")
    print(f"Wrote {review_path}")
    dropped = sum(d for _w, _h, _l, d in sanitized)
    if dropped:
        print(f"  dropped {dropped} rotated/vertical words (sidebars and watermarks, never transactions)")

    problems = verify(out_path, keep, args.redact, out_path.name, written)
    if problems:
        print("\nVERIFICATION FAILED - do not share this file:")
        for problem in problems[:20]:
            print(f"  - {problem}")
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
        return 1

    print(f"  checked: every word in the output is template, a date, a figure, or replaced ({len(kept)} kept verbatim)")
    if args.check_parse:
        print(f"  parse check: {check_parse(out_path)}")
    print(f"\nSkim {review_path.name} before sharing - it lists what was kept.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
