"""Turn a real bank statement into one that can be shared with developers.

Why this exists
---------------
Every parser in this project needs a real statement to be built and calibrated
against, and nobody can hand one over: it carries a name, a home address, an
account number and a year of spending. UOB got parsed because the author had
UOB statements; DBS and OCBC had to be written against their published layouts
instead (see `app/parsing/columnar.py`). This script is how that gap closes -
run it on your own statement and the result keeps everything a parser author
needs and drops what identifies you.

How it works, and why not a black box
-------------------------------------
Drawing a black rectangle over text in a PDF does not remove the text. It is
still in the content stream, still selectable, still there for anyone who runs
`pdftotext`. Redaction tools that get this wrong have leaked real documents.

So this does not edit your PDF. It reads the position, size and content of
every word, applies the redaction rules below, and *draws a new PDF from
scratch* containing only the surviving words. Anything that was not
deliberately re-drawn - the original text, images, annotations, attachments,
embedded metadata, form fields, any earlier revision left in the file - does
not exist in the output, because the output was built empty.

Each word is drawn into the exact bounding box the original occupied
(horizontally scaled to fit if the replacement text has a different natural
width), because that geometry is the thing a parser author needs: the parsers
in this project locate columns by x-position and group rows by y-position.

What it removes automatically
-----------------------------
* Account, card and reference numbers - any run of 6+ digits that isn't an
  amount or a date. Replaced consistently, so the same account number becomes
  the same placeholder everywhere and multi-statement grouping still works.
* NRIC/FIN, emails, phone numbers, postal codes.
* Transfer counterparty names - the payee or payer after a "To:" / "From:" /
  "to" / "from" marker, which on a Singapore statement is a real person.
  Pass --keep-counterparties if you'd rather review them yourself.
* Anything you name with --redact (repeatable). Use it for your own name,
  which no rule can find reliably.

What it deliberately keeps
--------------------------
Amounts and balances, merchant names, dates, and every piece of table
furniture. Those are what a parser has to read correctly - a fixture without
them proves nothing. That does mean the output still shows what you spent:
--redact-amounts replaces the figures if you'd rather share only the
structure, at the cost of the reconciliation checks a parser is tested with.

Using it
--------
    uv run python scripts/sanitize_statement.py statement.pdf \\
        --redact "YOUR NAME" --redact "SPOUSE NAME"

It writes `statement.sanitized.pdf` plus `statement.sanitized.review.txt`,
which lists every word that survived. **Read that file.** No automatic rule
knows your landlord's name or the nickname in a PayNow reference; the review
list is how you catch them, and you can re-run with more --redact values until
it's clean. The script also re-reads its own output and fails loudly if
anything it was told to remove is still findable.

Add --check-parse to confirm the sanitized file still parses, if the bank is
one this app already supports.
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
# What counts as personal
# --------------------------------------------------------------------------

#: An amount. Checked *before* the digit-run rule so "1,234.56" survives -
#: amounts are the one thing a parser fixture cannot do without.
#:
#: The three alternatives are deliberately not "any run of digits". A figure
#: qualifies by being comma-grouped, by having decimals, or by being short
#: enough that the identifier rule would ignore it anyway. A bare "123456"
#: matches none of them and is treated as an account number, which is the
#: safe way round: mistaking an identifier for an amount leaks it, while
#: mistaking an amount for an identifier only spoils the fixture.
MONEY_RE = re.compile(
    r"^\(?-?\$?(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{1,2}|\d{1,3})\)?\s*(?:CR|DR)?$",
    re.I,
)
#: A date in any of the shapes statements print. Also protected from the
#: digit-run rule, for the same reason.
DATE_RE = re.compile(
    r"^(\d{1,2}[-/.]\d{1,2}(?:[-/.]\d{2,4})?|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2})$"
)
#: Singapore NRIC/FIN: a letter, seven digits, a checksum letter.
NRIC_RE = re.compile(r"^[STFGM]\d{7}[A-Z]$", re.I)
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
#: A last-resort money guard for figures the strict pattern above misses -
#: "SGD1,234.56", "1,234.56-", anything ending in a two-decimal amount. Only
#: used to keep the digit-run rule off them.
MONEY_TAIL_RE = re.compile(r"\d[\d,]*\.\d{2}\s*(CR|DR)?[-)]?$", re.I)
#: How many digits in one token make it an identifier rather than a figure.
#: Six covers account numbers, card numbers, reference numbers, phone numbers
#: and postal codes; four-digit years and two-digit days stay clear of it.
IDENTIFIER_DIGIT_COUNT = 6

#: Words after which a Singapore statement prints a counterparty's name.
COUNTERPARTY_MARKERS = {"to", "to:", "from", "from:", "payee", "payee:", "beneficiary", "beneficiary:"}
#: Tokens that end a counterparty name - the transfer rails' own trailing
#: codes, which are structure rather than identity and worth keeping.
COUNTERPARTY_STOPWORDS = {
    "othr", "paynow", "transfer", "other", "fast", "payment", "receipt",
    "giro", "inb", "ref", "sgd", "via", "incoming", "outgoing", "-",
}

REDACTED_DIGIT_ALPHABET = "0123456789"
#: What a redacted NRIC becomes. Shaped like one on purpose, so a parser that
#: has to cope with the field still sees the field - and skipped by the
#: verifier below, which would otherwise flag this script's own output.
NRIC_PLACEHOLDER = "S0000000A"
#: Redacted addresses land on example.com, which RFC 2606 reserves precisely
#: so it can never belong to anyone. The verifier skips it for the same reason
#: it skips NRIC_PLACEHOLDER: it would otherwise flag this script's own work.
EMAIL_PLACEHOLDER_DOMAIN = "@example.com"


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


@dataclass
class Stats:
    numbers: int = 0
    nrics: int = 0
    emails: int = 0
    counterparties: int = 0
    named: int = 0
    amounts: int = 0
    dropped_rotated: int = 0


def _pseudonym_digits(original: str) -> str:
    """A stable stand-in for a number, same shape, same length.

    Deterministic so the same account number becomes the same placeholder in
    every statement you sanitize - a parser that groups transactions by
    account still has something to group by. Derived by hash rather than kept
    in a mapping file, so nothing on disk can be used to reverse it, and not
    reversible in any case: the hash is truncated to one digit per character.
    """
    digest = hashlib.sha256(original.encode()).hexdigest()
    out = []
    cursor = 0
    for char in original:
        if char.isdigit():
            out.append(REDACTED_DIGIT_ALPHABET[int(digest[cursor % len(digest)], 16) % 10])
            cursor += 1
        else:
            out.append(char)  # keep separators, so "123-456789-0" stays that shape
    return "".join(out)


def _pseudonym_text(original: str) -> str:
    """A stand-in for a name: same length, obviously not a name."""
    return ("SAMPLE" * ((len(original) // 6) + 1))[: len(original)]


def is_money(text: str) -> bool:
    return bool(MONEY_RE.match(text)) and any(c.isdigit() for c in text)


def is_date(text: str) -> bool:
    return bool(DATE_RE.match(text))


def group_lines(words: list[Word], y_tol: float = 3.0) -> list[list[Word]]:
    """Cluster words into physical lines, the way the parsers do.

    Both things this script does are line-scoped rather than page-scoped: a
    counterparty name follows its "To:" marker on the *same* row, and word
    spacing only has to be reproduced between words that sit side by side.
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
    """A word reduced to what makes it comparable: letters and digits, folded."""
    return re.sub(r"[^\w]", "", text).lower()


def _literal_matches(words: list[Word], literals: list[str]) -> set[int]:
    """Indices of the words covered by a --redact value.

    A multi-word value is matched as a *run* of consecutive words, and a
    single word by whole-word equality - never by substring. Substring
    matching looks more thorough and is worse: --redact "JANE TAN" would then
    strike every "STANDARD CHARTERED" on the statement, and a first name as
    ordinary as "Sam" would gut the merchant column. Over-redaction is not
    free here - what survives is the whole reason to share the file.
    """
    normalized = [_normalize(w.text) for w in words]
    hits: set[int] = set()
    for literal in literals:
        parts = [_normalize(part) for part in literal.split() if _normalize(part)]
        if not parts:
            continue
        for start in range(len(normalized) - len(parts) + 1):
            if all(normalized[start + n] == part for n, part in enumerate(parts)):
                hits.update(range(start, start + len(parts)))
    return hits


def redact_line(words: list[Word], literals: list[str], keep_counterparties: bool, redact_amounts: bool, stats: Stats) -> list[Word]:
    """Apply every redaction rule to one line's words, in order.

    One line at a time, because a "To:" marker only introduces a name on its
    own row: a page-wide scan would let a "to" at the end of one line redact
    the start of the next.
    """
    literal_hits = _literal_matches(words, literals)
    out: list[Word] = []
    counterparty_run = 0

    for index, word in enumerate(words):
        text = word.text
        lower = text.lower()

        # 1. Anything the contributor named. Checked first: if you said to
        #    remove it, no later rule gets to decide it looked like an amount.
        if index in literal_hits:
            stats.named += 1
            out.append(replace(word, text=_pseudonym_text(text)))
            counterparty_run = 0
            continue

        # 2. A counterparty name, i.e. whatever follows a "To:"/"From:" marker
        #    until the rail's own trailing codes resume.
        if counterparty_run > 0 and not keep_counterparties:
            # A counterparty's name is alphabetic. A digit-heavy token is a
            # reference number, so end the run and let the identifier rule
            # have it: both redact it, but that rule keeps its shape
            # ("PIB" + 16 digits), and the shape is what a parser author
            # needs to see. Ending the run here costs no privacy at all.
            looks_like_identifier = sum(c.isdigit() for c in text) >= IDENTIFIER_DIGIT_COUNT
            if lower.strip(":,-") in COUNTERPARTY_STOPWORDS or is_money(text) or is_date(text) or looks_like_identifier:
                counterparty_run = 0
            else:
                counterparty_run -= 1
                stats.counterparties += 1
                out.append(replace(word, text=_pseudonym_text(text)))
                continue
        if lower in COUNTERPARTY_MARKERS:
            # Cap the run: a marker inside an unusual description shouldn't
            # swallow the rest of the line.
            counterparty_run = 4

        if NRIC_RE.match(text):
            stats.nrics += 1
            out.append(replace(word, text=NRIC_PLACEHOLDER))
            continue

        if EMAIL_RE.match(text):
            stats.emails += 1
            out.append(replace(word, text=_pseudonym_text(text.split("@")[0]) + EMAIL_PLACEHOLDER_DOMAIN))
            continue

        if is_money(text):
            if redact_amounts:
                stats.amounts += 1
                out.append(replace(word, text=re.sub(r"\d", "0", text)))
            else:
                out.append(word)
            continue

        if is_date(text):
            out.append(word)
            continue

        # Counted rather than pattern-matched, because a reference number is
        # not always a bare run of digits: real statements print things like
        # "PIB0000000000000001" and "TRF-123456789", and a rule anchored on a
        # leading digit walks straight past both.
        digits = sum(c.isdigit() for c in text)
        if digits >= IDENTIFIER_DIGIT_COUNT and not MONEY_TAIL_RE.search(text):
            stats.numbers += 1
            out.append(replace(word, text=_pseudonym_digits(text)))
            continue

        out.append(word)

    return out


# --------------------------------------------------------------------------
# Reading and rebuilding
# --------------------------------------------------------------------------


def read_pages(path: Path, password: str | None) -> list[tuple[float, float, list[Word]]]:
    """Every page as (width, height, words), decrypting in memory if needed."""
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
            words = []
            rotated = 0
            for w in page.extract_words(use_text_flow=False, keep_blank_chars=False, extra_attrs=["size", "fontname", "upright"]):
                if not w.get("upright", True):
                    # Vertical text is a sidebar or a watermark, never a
                    # transaction, and reproducing its geometry faithfully is
                    # more trouble than it is worth.
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

    for width, height, lines, _rotated in pages:
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
                # first and only falls back to a gap-width threshold (3pt by
                # default) otherwise - and inter-word gaps on a real statement
                # are routinely under 3pt, because the original PDF had an
                # actual space character there to do the splitting. Drawing
                # each word on its own removes those spaces, so they have to be
                # put back, or every parser in this project (all of which go
                # through extract_words) sees one giant token per line.
                if index + 1 < len(line):
                    gap_start, gap_end = word.x1, line[index + 1].x0
                    if gap_end > gap_start:
                        _draw_fitted(c, " ", font, size, gap_start, gap_end, y)
        c.showPage()
    c.save()


def _draw_fitted(c: canvas.Canvas, text: str, font: str, size: float, x0: float, x1: float, y: float) -> None:
    """Draw `text` so it occupies exactly the box [x0, x1].

    Horizontally scaled to fit, because the geometry is the point: the parsers
    bucket words into columns by x0 and x1, so a replacement that renders
    wider or narrower than the text it replaces would move a word into the
    next column. The glyphs being slightly condensed is a cost worth paying.
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


def write_review(path: Path, pages, stats: Stats, source_name: str) -> None:
    """List every word that survived, so a human can check what's left.

    This is the part that actually makes the tool safe. The automatic rules
    catch structured identifiers; they cannot know that "MRS LIM" in a GIRO
    description is your landlord. Reading this file is the step where that
    gets caught.
    """
    seen: dict[str, int] = {}
    for _w, _h, lines, _r in pages:
        for line in lines:
            for word in line:
                token = word.text.strip()
                if token and not is_money(token) and not is_date(token):
                    seen[token] = seen.get(token, 0) + 1

    lines = [
        f"Review list for the sanitized copy of {source_name}",
        "",
        "Every distinct word left in the output is listed below (amounts and dates",
        "omitted - those are kept on purpose). Scan it for anything personal that",
        "the automatic rules could not know about: your landlord's name, a nickname",
        "in a PayNow reference, an employer you'd rather not name, a club or clinic.",
        "",
        "For each one you find, re-run with --redact \"THAT TEXT\" until this list is",
        "clean. Only then is the PDF safe to attach to an issue.",
        "",
        f"Redacted automatically: {stats.numbers} numbers, {stats.nrics} NRIC/FIN, "
        f"{stats.emails} emails, {stats.counterparties} counterparty name words, "
        f"{stats.named} words you named"
        + (f", {stats.amounts} amounts" if stats.amounts else ""),
        "",
        f"--- {len(seen)} distinct words remaining ---",
    ]
    lines += [f"{count:>5}  {token}" for token, count in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify(out_path: Path, literals: list[str]) -> list[str]:
    """Re-read the output and report anything that should not have survived.

    A redaction tool that trusts its own rules is how documents leak. This
    reads the finished file back the way a recipient would and looks for the
    patterns the rules were supposed to remove.
    """
    with pdfplumber.open(out_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    problems = []
    lowered = text.lower()
    for literal in literals:
        if literal.strip() and literal.lower() in lowered:
            problems.append(f'the text you asked to remove is still present: "{literal}"')
    for token in re.findall(r"\S+", text):
        if NRIC_RE.match(token) and token != NRIC_PLACEHOLDER:
            problems.append(f"an NRIC/FIN survived: {token}")
        elif EMAIL_RE.match(token) and not token.lower().endswith(EMAIL_PLACEHOLDER_DOMAIN):
            problems.append(f"an email address survived: {token}")
    return problems


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
        description="Strip personal data from a bank statement PDF, keeping its layout intact.",
        epilog="Read the generated .review.txt before sharing the result.",
    )
    parser.add_argument("pdf", type=Path, help="the statement to sanitize")
    parser.add_argument("-o", "--output", type=Path, help="output path (default: <name>.sanitized.pdf)")
    parser.add_argument("--password", help="password, if the statement is protected (never stored)")
    parser.add_argument(
        "--redact",
        action="append",
        default=[],
        metavar="TEXT",
        help="extra text to remove - your name, a family member, an employer. Repeatable.",
    )
    parser.add_argument(
        "--keep-counterparties",
        action="store_true",
        help="keep PayNow/transfer payee and payer names instead of replacing them",
    )
    parser.add_argument(
        "--redact-amounts",
        action="store_true",
        help="also blank out every figure. Shares the structure only, and defeats the "
        "reconciliation checks a parser is tested against - prefer leaving it off.",
    )
    parser.add_argument("--check-parse", action="store_true", help="try parsing the result with this app's parsers")
    args = parser.parse_args(argv)

    if not args.pdf.is_file():
        raise SystemExit(f"No such file: {args.pdf}")

    out_path = args.output or args.pdf.with_name(args.pdf.stem + ".sanitized.pdf")
    review_path = out_path.with_suffix(".review.txt")

    stats = Stats()
    pages = read_pages(args.pdf, args.password)
    sanitized = [
        (
            width,
            height,
            [
                redact_line(line, args.redact, args.keep_counterparties, args.redact_amounts, stats)
                for line in group_lines(words)
            ],
            rotated,
        )
        for width, height, words, rotated in pages
    ]
    stats.dropped_rotated = sum(rotated for _w, _h, _lines, rotated in sanitized)

    notice = "Synthetic/sanitized sample - personal data removed by scripts/sanitize_statement.py"
    write_pdf(out_path, sanitized, notice)
    write_review(review_path, sanitized, stats, args.pdf.name)

    print(f"Wrote {out_path}")
    print(f"Wrote {review_path}")
    print(
        f"  redacted: {stats.numbers} numbers, {stats.nrics} NRIC/FIN, {stats.emails} emails, "
        f"{stats.counterparties} counterparty name words, {stats.named} words you named"
        + (f", {stats.amounts} amounts" if stats.amounts else "")
    )
    if stats.dropped_rotated:
        print(f"  dropped {stats.dropped_rotated} rotated/vertical words (sidebars and watermarks, never transactions)")

    problems = verify(out_path, args.redact)
    if problems:
        print("\nVERIFICATION FAILED - do not share this file:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("  verified: no NRIC, email, or --redact text found in the output")

    if args.check_parse:
        print(f"  parse check: {check_parse(out_path)}")

    print(f"\nNow read {review_path.name} and re-run with --redact for anything personal still listed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
