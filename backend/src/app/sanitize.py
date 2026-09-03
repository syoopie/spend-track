"""Rebuild a bank statement PDF with everything personal replaced by its shape.

This is the domain half of the statement sanitizer. `scripts/sanitize_statement.py`
is a thin CLI over it and `routers/contribute.py` is the in-app one; the rules
below are the only copy of them, so the two cannot drift.

It lives in the package rather than beside the CLI because
`packaging/spend-track.spec` bundles `src/app` and not `scripts/`, so anything
under `scripts/` is unreachable from a packaged desktop build. It sits at
`app/sanitize.py` rather than under `app/parsing/` because it imports
`parsing.registry` and `parsing.pdf_io`, and nesting it there invites a cycle.

The rule is default-deny
------------------------
A word survives only if it is positively recognized as the bank's own template
wording, a date, a figure, or something the caller named with `keep`. Anything
else - anything nobody anticipated - is replaced with its shape. That is what
makes this small: an earlier version worked the other way round, spotting the
personal words and keeping the rest, and needed rules for NRIC, emails, phone
numbers, counterparty names and split digit runs, each of which could miss.

It rebuilds rather than edits. Drawing a black box over text leaves the text in
the content stream, which is how real redaction failures happen. Reading every
word's geometry and drawing a fresh document means the original text, images,
annotations, metadata and any earlier incremental-save revision are absent by
construction.

Verification is exhaustive, not heuristic
-----------------------------------------
`verify` re-reads the finished bytes and reports every word it cannot account
for. There is no "looks personal" judgement anywhere in it.

Note what that cannot see: a file with no extractable text at all - a scan or a
photo - has no survivors and so is vacuously clean. `SanitizeResult.word_count`
is how a caller tells that case apart, and it must, because a blank output that
passes every check is the worst thing this module can hand back.

`sanitize` always returns the rendered bytes, even when `problems` is non-empty.
Whether a failed verification means refusing the file or warning loudly and
handing it over is the caller's policy: the CLI refuses and still writes the
file so a maintainer can inspect what leaked, the endpoint warns and offers the
download.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

import pdfplumber
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.parsing.base import UnparseableStatementError
from app.parsing.columnar import StatementReconciliationError
from app.parsing.pdf_io import EncryptedPdfError, IncorrectPasswordError, open_pdf
from app.parsing.registry import detect_and_parse

__all__ = [
    "AccountSummary",
    "CHROME_VOCABULARY",
    "DATE_RE",
    "EncryptedPdfError",
    "IncorrectPasswordError",
    "MONEY_RE",
    "ParseCheck",
    "SAMPLE_NOTICE",
    "SanitizeResult",
    "Word",
    "check_parse",
    "group_lines",
    "is_chrome",
    "is_date",
    "is_money",
    "is_year",
    "keeps",
    "kept_words",
    "normalize_keep",
    "read_pages",
    "redact_line",
    "render_pdf",
    "sanitize",
    "surviving_oddities",
    "verify",
]

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
#: a miss is only that the sample needs a `keep` to parse, which the parse
#: check surfaces immediately.
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

#: Drawn into the output's Subject. Names no script, because the person who
#: produced the file may only ever have clicked a button in the app.
SAMPLE_NOTICE = "Sanitized statement sample: personal details replaced with their shape"


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


#: One page as read: width, height, its words, and how many rotated words were
#: dropped. `render_pdf`, `kept_words` and `surviving_oddities` take the same
#: shape after `group_lines` has nested the words into lines.
Page = tuple[float, float, list[Word], int]
LinedPage = tuple[float, float, list[list[Word]], int]


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
    """Everything this module is willing to leave in the output verbatim."""
    return is_chrome(text) or is_year(text) or is_date(text) or text.lower() in keep


def normalize_keep(phrases: Sequence[str]) -> frozenset[str]:
    """Split each phrase into words and lower-case them.

    Matching is per word, so `keep=["SAMPLE MART"]` has to become {"sample",
    "mart"} before it can preserve anything. Hoisted out of the CLI's argument
    handling so no second caller can normalize differently and silently keep a
    different set of words than `--keep` does.
    """
    return frozenset(word.lower() for phrase in phrases for word in phrase.split())


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
    """Indices of the words covered by a `redact` value.

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
    literals: Sequence[str] = (),
    keep: frozenset[str] = frozenset(),
    redact_amounts: bool = False,
    written: set[str] | None = None,
) -> list[Word]:
    """Replace every word that isn't template, a date or a figure.

    `redact` is still worth having even under default-deny, for the one case
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


def read_pages(data: bytes, password: str | None = None) -> list[Page]:
    """Every page as (width, height, words, dropped), decrypting in memory.

    Propagates `EncryptedPdfError` / `IncorrectPasswordError` rather than
    turning them into a message. A `SystemExit` here would be a `BaseException`
    raised inside an anyio worker thread, which walks straight past Starlette's
    exception middleware; the CLI is the only caller entitled to exit.
    """
    pdf = open_pdf(data, password)

    pages: list[Page] = []
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


def render_pdf(pages: Sequence[LinedPage], notice: str, *, invariant: bool = True) -> bytes:
    """Draw a fresh PDF containing the surviving words and nothing else.

    `invariant` zeroes the creation and modification dates. Without it reportlab
    stamps the author's local clock *and timezone* into every file - real output
    carried `/CreationDate (D:20260903202532+08'00')`, which places its author in
    Singapore and times the sanitizing run against whenever the sample was
    posted. It also makes the same input render to the same bytes, so a
    contributor can re-run and diff.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, invariant=1 if invariant else 0)
    c.setTitle("Sanitized bank statement sample")
    c.setAuthor("SpendTrack")
    c.setSubject(notice)
    c.setCreator("SpendTrack statement sanitizer")

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
    return buf.getvalue()


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


def verify(
    pdf: bytes,
    keep: frozenset[str],
    literals: Sequence[str],
    output_name: str,
    written: set[str],
) -> list[str]:
    """Re-read the finished bytes the way a recipient would.

    Default-deny makes this exhaustive rather than heuristic: every word in a
    finished file must be template, a date, a figure, something the contributor
    asked to keep, or text this module itself wrote. Anything else slipped
    through, and there is no need to guess whether it looks personal - it
    should not be there at all.

    `written` is needed because a replaced *number* is indistinguishable by
    inspection from one that survived: both are digit strings, and the whole
    point of the check is to catch the rule having failed to fire. Replaced
    words are still looked for in the finished file rather than assumed
    present, so this stays a check on the artifact and not on the model.

    One pdfplumber pass, because the endpoint re-runs the whole pipeline on
    every edit a contributor makes.
    """
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        tokens = [w["text"] for page in doc.pages for w in page.extract_words()]
        text = "\n".join(page.extract_text() or "" for page in doc.pages).lower()

    survivors = sorted(
        {
            token
            for token in tokens
            if any(c.isalnum() for c in token)
            and token not in written
            and not is_money(token)
            and not keeps(token, keep)
        }
    )
    problems = [f"a word survived that is not template, a date or a figure: {word}" for word in survivors]

    for literal in literals:
        if literal.strip() and literal.lower() in text:
            problems.append(f'the text you asked to remove is still present: "{literal}"')

    # The file name travels with the file, and is what gets attached to an
    # issue. Checked against the *output* name, since renaming the output is
    # the fix and reading the input's name would refuse to accept it.
    for literal in literals:
        for part in literal.split():
            if len(part) >= 3 and part.lower() in output_name.lower():
                problems.append(f'the output file name "{output_name}" contains "{part}" - pass --output to rename it')
    return problems


def kept_words(pages: Sequence[LinedPage], written: set[str]) -> list[str]:
    """The words kept verbatim, so a human can confirm none is personal.

    Short by construction - it is the template vocabulary that appeared in this
    statement, tens of words rather than hundreds - because everything else was
    replaced rather than judged.

    Filtered on `isalpha`, so it structurally cannot contain an amount, a date,
    a house number or a `#12` unit, all of which survive. Any copy written over
    this list has to say so rather than implying the list is the whole story.
    """
    return sorted(
        {
            word.text
            for _w, _h, lines, _d in pages
            for line in lines
            for word in line
            if any(c.isalpha() for c in word.text) and word.text not in written
        }
    )


def surviving_oddities(pages: Sequence[LinedPage], written: set[str]) -> list[str]:
    """Surviving tokens with no letter in them that are not a figure or a date.

    `kept_words` cannot see these, and this is where a stray identifier would
    actually hide: a postal code, a unit number, a reference that happens to be
    all digits. Short enough to read, because everything accounted for by the
    money, date and year rules is already excluded.
    """
    return sorted(
        {
            word.text
            for _w, _h, lines, _d in pages
            for line in lines
            for word in line
            if word.text not in written
            and any(c.isalnum() for c in word.text)
            and not any(c.isalpha() for c in word.text)
            and not is_money(word.text)
            and not is_date(word.text)
            and not is_year(word.text)
        }
    )


@dataclass(frozen=True)
class AccountSummary:
    account_type: str
    transaction_count: int


@dataclass(frozen=True)
class ParseCheck:
    """Whether this app's own parsers can read the sanitized result.

    Not reading a bank yet is exactly why the sample is wanted, so this is
    information rather than an error.

    `detail` carries the parser's own message and MAY QUOTE THE CONTRIBUTOR'S
    REAL FIGURES: `StatementReconciliationError` subclasses
    `UnparseableStatementError` and prints both the statement's printed total
    and the sum it read. Show it on screen, never put it in a URL, an issue
    body or anything else that leaves the machine. `account_summaries` is built
    from parser output only, never from an exception, which is what makes it
    safe to display and to send.
    """

    parsed: bool
    bank_name: str | None
    account_summaries: list[AccountSummary]
    failure_kind: Literal["unrecognized", "reconciliation", "parser_error"] | None
    detail: str


def check_parse(pdf: bytes) -> ParseCheck:
    try:
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            statement = detect_and_parse(doc.pages)
    except StatementReconciliationError as exc:
        return ParseCheck(False, None, [], "reconciliation", str(exc))
    except UnparseableStatementError as exc:
        return ParseCheck(False, None, [], "unrecognized", str(exc))
    except Exception as exc:  # a parser bug is exactly what a new sample exposes
        return ParseCheck(False, None, [], "parser_error", f"{type(exc).__name__}: {exc}")
    return ParseCheck(
        True,
        statement.bank_name,
        [AccountSummary(a.account_type, len(a.transactions)) for a in statement.accounts],
        None,
        "",
    )


@dataclass(frozen=True)
class SanitizeResult:
    #: Always populated, even when `problems` is non-empty. Refusing or warning
    #: is the caller's policy, and both callers need the bytes either way.
    pdf: bytes
    problems: list[str]
    kept: list[str]
    oddities: list[str]
    page_count: int
    #: Words read from the *input*. Zero means it had no extractable text at
    #: all - a scan or a photo - which passes every check vacuously and yields
    #: a blank file. Callers must handle that case explicitly.
    word_count: int
    rotated_dropped: int


def sanitize(
    data: bytes,
    *,
    password: str | None = None,
    redact: Sequence[str] = (),
    keep: Sequence[str] = (),
    redact_amounts: bool = False,
    output_name: str = "sample.pdf",
) -> SanitizeResult:
    """Read, redact, rebuild and re-check, in one pass with no state kept.

    Raises `EncryptedPdfError` / `IncorrectPasswordError` from `read_pages`.
    `keep` is normalized here rather than by the caller, so the endpoint and
    the CLI cannot preserve different words for the same phrase.
    """
    normalized_keep = normalize_keep(keep)
    pages = read_pages(data, password)
    written: set[str] = set()
    sanitized: list[LinedPage] = [
        (
            width,
            height,
            [redact_line(line, redact, normalized_keep, redact_amounts, written) for line in group_lines(words)],
            dropped,
        )
        for width, height, words, dropped in pages
    ]

    pdf = render_pdf(sanitized, SAMPLE_NOTICE)
    return SanitizeResult(
        pdf=pdf,
        problems=verify(pdf, normalized_keep, redact, output_name, written),
        kept=kept_words(sanitized, written),
        oddities=surviving_oddities(sanitized, written),
        page_count=len(pages),
        word_count=sum(len(words) for _w, _h, words, _d in pages),
        rotated_dropped=sum(dropped for _w, _h, _words, dropped in pages),
    )
