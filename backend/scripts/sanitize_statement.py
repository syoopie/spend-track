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
  amount or a date, **including one the statement split across words**, as
  they routinely do ("4111 1111 1111 1234", "9123 4567"). Replaced
  consistently, so the same number becomes the same placeholder however it was
  grouped, and multi-statement account grouping still works.
* NRIC/FIN, emails, phone numbers, postal codes.
* Names introduced by something: a payee or payer after "To:" / "From:", or a
  name after an honorific ("GIRO Payment MRS LIM SIEW KHENG"). Pass
  --keep-counterparties if you'd rather review those yourself.
* Anything you name with --redact (repeatable), matched however the PDF split
  it - type "Anne-Marie" once and it matches "Anne Marie" too.

What it cannot find, and why you have to look
---------------------------------------------
A name that nothing introduces. Your own, in the address block. A joint
holder's. A landlord's, a street's. No rule distinguishes those from a
merchant, and one that guessed would be the one that quietly dropped half your
transaction descriptions.

So the run is not finished when the script exits 0. It writes a review file
whose first section lists every name-shaped phrase that survived, with the line
each came from, and that list is short by design - re-run with --redact for
each one until it holds nothing personal. The script's own checks confirm the
rules did what they were asked; they are not a clean bill of health, and the
output never claims to be one.

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

It writes `statement.sanitized.pdf` plus `statement.sanitized.review.txt`.
**Read that file**, then run it again with what it flagged.

Before finishing it re-reads its own output the way a recipient would, and
refuses the file if anything it removed is still findable anywhere in it -
including in the output's *name*, since "JaneWong-Jan2024.pdf" identifies its
owner as well as its contents do. Use --output to name the result something
neutral.

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

#: Words after which a statement prints a person's name. The transfer markers
#: are the common case; the honorifics catch the other one, a GIRO or standing
#: instruction naming its payee ("GIRO Payment MRS LIM SIEW KHENG") with no
#: transfer preposition anywhere on the line. "dr" is deliberately absent - it
#: is also the debit marker that follows an amount.
COUNTERPARTY_MARKERS = {
    "to", "to:", "from", "from:", "payee", "payee:", "beneficiary", "beneficiary:",
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "mdm", "mdm.", "miss", "prof",
}
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
    # Hashed on the digits alone, not the separators, so "4111-1111-1111-1234",
    # "4111 1111 1111 1234" and "4111111111111234" all land on the same
    # placeholder. A statement is free to group one number differently in two
    # places, and a parser grouping by account must still see one account.
    digest = hashlib.sha256("".join(c for c in original if c.isdigit()).encode()).hexdigest()
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


def _pseudonymize_run(texts: list[str]) -> list[str]:
    """Pseudonymise several words that together spell one identifier.

    The digits are concatenated, replaced as a unit and dealt back out in the
    original groupings, so a card number keeps its 4-4-4-4 shape and lands on
    the same placeholder as the same number written without spaces.
    """
    digits = "".join(c for text in texts for c in text if c.isdigit())
    replacement = _pseudonym_digits(digits)
    out, cursor = [], 0
    for text in texts:
        chars = []
        for char in text:
            if char.isdigit():
                chars.append(replacement[cursor])
                cursor += 1
            else:
                chars.append(char)
        out.append("".join(chars))
    return out


def _looks_like_spaced_date(texts: list[str]) -> bool:
    """"15 03 2024" - a date written with spaces, not an identifier."""
    if len(texts) != 3:
        return False
    day, month, year = texts
    return len(day) <= 2 and len(month) <= 2 and len(year) == 4 and int(month) <= 12


def _digit_run_replacements(words: list[Word]) -> dict[int, str]:
    """Find identifiers that the PDF split across several words.

    This is the leak that matters most, because it is both invisible and
    common: statements routinely print a card number as "4111 1111 1111 1234"
    and a phone as "9123 4567". Every one of those pieces is four digits -
    under any per-word identifier threshold - so a word-at-a-time rule passes
    over all of them and the full number sails through intact.

    So adjacent pure-digit words that are close enough together to be one
    printed number are pseudonymised as a unit. "Close enough" is measured
    against the font size: the gap inside a grouped number is about a space
    wide, while the gap between two table columns is an order of magnitude
    bigger, so there is a lot of daylight between the two cases.
    """
    replacements: dict[int, str] = {}
    start = 0
    while start < len(words):
        end = start
        while (
            end + 1 < len(words)
            and _is_bare_digits(words[end + 1].text)
            and _is_bare_digits(words[end].text)
            and words[end + 1].x0 - words[end].x1 <= max(2.5, words[end].size * 0.8)
        ):
            end += 1
        run = words[start : end + 1]
        texts = [w.text for w in run]
        if (
            len(run) >= 2
            and all(_is_bare_digits(t) for t in texts)
            and sum(len(t) for t in texts) >= IDENTIFIER_DIGIT_COUNT
            and not _looks_like_spaced_date(texts)
        ):
            for offset, replacement in enumerate(_pseudonymize_run(texts)):
                replacements[start + offset] = replacement
        start = end + 1
    return replacements


def _is_bare_digits(text: str) -> bool:
    """Digits only, bar a leading + (as in "+65"). Deliberately excludes
    anything with a comma or a decimal point, so an amount can never be swept
    into a digit run."""
    stripped = text.lstrip("+")
    return bool(stripped) and stripped.isdigit()


def _normalize(text: str) -> str:
    """A word reduced to what makes it comparable: letters and digits, folded."""
    return re.sub(r"[^\w]", "", text).lower()


def _literal_matches(words: list[Word], literals: list[str]) -> set[int]:
    """Indices of the words covered by a --redact value.

    Matched against whole words joined end to end, never as a substring.
    Substring matching looks more thorough and is worse: --redact "JANE TAN"
    would then strike every "STANDARD CHARTERED" on the statement, and a first
    name as ordinary as "Sam" would gut the merchant column. Over-redaction is
    not free here - what survives is the whole reason to share the file.

    Comparing the joined run against the joined literal, with punctuation
    stripped from both, means the contributor does not have to guess how the
    PDF happened to split their name. "Anne-Marie" typed once matches whether
    the statement prints it as one word, as "Anne Marie", or as "Anne-Marie" -
    and a name only ever needs typing in the form the human recognizes.
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


def redact_line(words: list[Word], literals: list[str], keep_counterparties: bool, redact_amounts: bool, stats: Stats) -> list[Word]:
    """Apply every redaction rule to one line's words, in order.

    One line at a time, because a "To:" marker only introduces a name on its
    own row: a page-wide scan would let a "to" at the end of one line redact
    the start of the next.
    """
    literal_hits = _literal_matches(words, literals)
    digit_runs = _digit_run_replacements(words)
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

        # 2. A piece of an identifier the PDF split across words - a card
        #    number or phone number printed in groups. Ahead of the
        #    counterparty rule so a name run can't swallow one of the pieces
        #    and destroy the number's shape.
        if index in digit_runs:
            stats.numbers += 1
            out.append(replace(word, text=digit_runs[index]))
            counterparty_run = 0
            continue

        # 3. A counterparty name, i.e. whatever follows a "To:"/"From:" marker
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


#: Capitalised words that head a statement's furniture rather than a person.
#: Only used to keep the name-candidate list below short enough to actually
#: get read - a false negative here costs nothing, since the full word list
#: follows underneath.
FURNITURE_WORDS = {
    "account", "accounts", "statement", "statements", "balance", "total", "date",
    "dates", "description", "withdrawal", "withdrawals", "deposit", "deposits",
    "transaction", "transactions", "page", "currency", "singapore", "dollar",
    "credit", "debit", "card", "cards", "bank", "limited", "ltd", "pte", "period",
    "summary", "details", "previous", "new", "sub", "brought", "carried", "forward",
    "payment", "payments", "transfer", "amount", "ref", "no", "value", "posting",
    "contact", "tel", "mobile", "email", "nric", "fin", "uen", "joint", "holder",
    "secondary", "held", "by",
    # The transfer rails' own wording, which sits right where a name would and
    # would otherwise fill the list with "FAST PAYMENT" and "GIRO Payment".
    "fast", "paynow", "giro", "nets", "inward", "outward", "incoming", "outgoing",
    "othr", "receipt", "purchase", "bill", "salary",
}


def _name_candidates(pages, placeholders: set[str]) -> list[tuple[str, str]]:
    """Runs of capitalised words that could be somebody's name.

    A flat frequency-sorted word list is not actually reviewable: the names in
    the leak hunt that produced this function were scattered through 72 entries,
    most of them the script's own placeholder output. Person names, street
    names and company names all share one shape though - consecutive
    capitalised alphabetic words - and that shape is rare enough on a statement
    to make a short list. Merchants land in it too; that is fine, since the
    list exists to be skimmed rather than trusted.
    """
    candidates: dict[str, str] = {}
    for _w, _h, lines, _r in pages:
        for line in lines:
            run: list[str] = []
            for word in line:
                token = word.text.strip()
                if token and token not in placeholders and _looks_like_name_word(token):
                    run.append(token)
                    continue
                _record_candidate(candidates, run, line)
                run = []
            _record_candidate(candidates, run, line)
    return sorted(candidates.items())


def _looks_like_name_word(token: str) -> bool:
    core = token.strip(".,:;()")
    if not core or not core[0].isupper():
        return False
    return all(c.isalpha() or c in "-'." for c in core)


def _record_candidate(candidates: dict[str, str], run: list[str], line) -> None:
    if len(run) < 2:
        return
    # Dropped only when *every* word is furniture or a marker. A run with one
    # unrecognized word in it stays, because that word is exactly what a name
    # looks like - dropping on "any" instead of "all" would hide "KAMALA DEVI"
    # the moment it followed a word this set happens to know.
    if all(word.strip(".,:;()").lower() in FURNITURE_WORDS | COUNTERPARTY_MARKERS for word in run):
        return
    phrase = " ".join(run)
    candidates.setdefault(phrase, " ".join(w.text for w in line))


def write_review(path: Path, pages, stats: Stats, source_name: str, placeholders: set[str]) -> int:
    """List what survived, so a human can check it. Returns the candidate count.

    This is the part that actually makes the tool safe. The automatic rules
    catch structured identifiers; they cannot know that "MRS LIM" in a GIRO
    description is your landlord, and no rule ever will. Reading this file is
    the step where that gets caught, so it has to be genuinely readable: the
    name-shaped survivors come first with the line each appeared on, and the
    script's own placeholder output is left out entirely as the noise it is.
    """
    seen: dict[str, int] = {}
    for _w, _h, lines, _r in pages:
        for line in lines:
            for word in line:
                token = word.text.strip()
                if token and token not in placeholders and not is_money(token) and not is_date(token):
                    seen[token] = seen.get(token, 0) + 1

    candidates = _name_candidates(pages, placeholders)

    out = [
        f"Review list for the sanitized copy of {source_name}",
        "",
        "The automatic rules removed the identifiers they can recognize. They",
        "cannot recognize a name that isn't introduced by anything - your own,",
        "a joint holder's, a landlord's, a street. Those are what this file is",
        "for, and nothing else will catch them.",
        "",
        "Re-run with --redact \"THAT TEXT\" for each one you find, until this",
        "file is clean. Only then is the PDF safe to attach to an issue.",
        "",
        f"Redacted automatically: {stats.numbers} numbers, {stats.nrics} NRIC/FIN, "
        f"{stats.emails} emails, {stats.counterparties} counterparty name words, "
        f"{stats.named} words you named"
        + (f", {stats.amounts} amounts" if stats.amounts else ""),
        "",
        "=" * 70,
        f"CHECK THESE FIRST - {len(candidates)} name-shaped phrases survived",
        "=" * 70,
        "Anything here that names a person, a household or an address needs a",
        "--redact. Merchant and bank names belong here too and are fine to keep.",
        "",
    ]
    for phrase, context in candidates:
        out.append(f"  {phrase}")
        if context.strip() != phrase:
            out.append(f"      on: {context.strip()[:100]}")
    out += [
        "",
        "=" * 70,
        f"EVERYTHING ELSE - {len(seen)} distinct words (amounts, dates and",
        "replaced text omitted)",
        "=" * 70,
    ]
    out += [f"{count:>5}  {token}" for token, count in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(candidates)


#: A numeric fragment shorter than this is not cross-checked: a card number's
#: "0000" reappears innocently all over a statement, and a check that cries
#: wolf gets ignored, which costs more than it catches.
CROSS_CHECK_MIN_DIGITS = 5
#: An *alphabetic* fragment is cross-checked from two characters up, which is
#: much lower, and deliberately. Singaporean names are built from exactly these
#: pieces - TAN, WEI, LIM, LEE, NG, ONG - so a length threshold tuned to look
#: sensible in the abstract skips precisely the tokens that identify people
#: here. The adversarial suite caught this: "TAN WEI MING" was removed after a
#: "To:" on one page and left standing on another, and every one of its three
#: parts fell under a five-character bar.
CROSS_CHECK_MIN_LETTERS = 2


def verify(out_path: Path, literals: list[str], removed: set[str] | None = None, source_name: str = "") -> list[str]:
    """Re-read the output and report anything that should not have survived.

    A redaction tool that trusts its own rules is how documents leak, so this
    reads the finished file back the way a recipient would. Three checks:

    * the literals the contributor named are gone;
    * no NRIC or email matching the patterns the rules remove is left;
    * **nothing the redactor decided to remove is still somewhere in the
      output.** That last one is the general net. The rules run per line, so a
      name caught after a "To:" on page 1 and printed bare on page 4 is
      removed once and missed once - and only a whole-document comparison
      notices. It also catches a rule that fires inconsistently for any reason
      nobody has thought of yet, which is the failure mode worth insuring
      against.

    What it cannot do is find PII the rules never recognized at all; that is
    the review file's job, and the caller must not report otherwise.
    """
    with pdfplumber.open(out_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    problems = []
    lowered = text.lower()
    for literal in literals:
        if literal.strip() and literal.lower() in lowered:
            problems.append(f'the text you asked to remove is still present: "{literal}"')

    tokens = re.findall(r"\S+", text)
    for token in tokens:
        if NRIC_RE.match(token) and token != NRIC_PLACEHOLDER:
            problems.append(f"an NRIC/FIN survived: {token}")
        elif EMAIL_RE.match(token) and not token.lower().endswith(EMAIL_PLACEHOLDER_DOMAIN):
            problems.append(f"an email address survived: {token}")

    surviving = {t.strip(".,:;()") for t in tokens}
    for original in sorted(removed or ()):
        stripped = original.strip(".,:;()")
        if not stripped or stripped not in surviving:
            continue
        long_enough = (
            len(stripped) >= CROSS_CHECK_MIN_LETTERS
            if stripped.isalpha()
            else len(stripped) >= CROSS_CHECK_MIN_DIGITS
        )
        if long_enough:
            problems.append(f"redacted elsewhere but still present here: {original}")

    # The file name travels with the file. "JaneWong-Jan2024.pdf" identifies
    # its owner as well as anything inside it does. Checked against the *output*
    # name, since that is the one that gets attached - passing --output is the
    # fix, and reading the input's name instead would refuse to accept it.
    for literal in literals:
        for part in literal.split():
            if len(part) >= 3 and part.lower() in source_name.lower():
                problems.append(
                    f'the output file name "{source_name}" contains "{part}" - pass --output to rename it'
                )
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

    original = [(width, height, group_lines(words), rotated) for width, height, words, rotated in pages]
    sanitized = [
        (
            width,
            height,
            [redact_line(line, args.redact, args.keep_counterparties, args.redact_amounts, stats) for line in lines],
            rotated,
        )
        for width, height, lines, rotated in original
    ]
    stats.dropped_rotated = sum(rotated for _w, _h, _lines, rotated in sanitized)

    # The two page lists are index-parallel, so a word that changed tells us
    # both what was removed (for the cross-check) and what the replacement text
    # is (so the review file can leave the script's own output out of it).
    removed: set[str] = set()
    placeholders: set[str] = set()
    for (_w, _h, before_lines, _r), (_w2, _h2, after_lines, _r2) in zip(original, sanitized):
        for before_line, after_line in zip(before_lines, after_lines):
            for before, after in zip(before_line, after_line):
                if before.text != after.text:
                    removed.add(before.text)
                    placeholders.add(after.text)

    notice = "Synthetic/sanitized sample - personal data removed by scripts/sanitize_statement.py"
    write_pdf(out_path, sanitized, notice)
    candidate_count = write_review(review_path, sanitized, stats, args.pdf.name, placeholders)

    print(f"Wrote {out_path}")
    print(f"Wrote {review_path}")
    print(
        f"  redacted: {stats.numbers} numbers, {stats.nrics} NRIC/FIN, {stats.emails} emails, "
        f"{stats.counterparties} counterparty name words, {stats.named} words you named"
        + (f", {stats.amounts} amounts" if stats.amounts else "")
    )
    if stats.dropped_rotated:
        print(f"  dropped {stats.dropped_rotated} rotated/vertical words (sidebars and watermarks, never transactions)")

    problems = verify(out_path, args.redact, removed, out_path.name)
    if problems:
        print("\nVERIFICATION FAILED - do not share this file:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    # Deliberately not phrased as an all-clear. These checks confirm the rules
    # did what they were asked; they say nothing about a name no rule was ever
    # going to recognize, and an earlier version of this line read as "no PII
    # found" over five such names sitting in the output.
    print("  checks passed: everything the rules removed is gone from the output")

    if args.check_parse:
        print(f"  parse check: {check_parse(out_path)}")

    print()
    if candidate_count:
        print("NOT DONE YET. The rules cannot find a name that nothing introduces -")
        print(f"yours, a joint holder's, a landlord's, a street. {candidate_count} name-shaped")
        print(f"phrase{'s' if candidate_count != 1 else ''} survived and need your eyes:")
        print(f"    {review_path}")
        print("Re-run with --redact for each one, until that file is clean.")
    else:
        print("No name-shaped phrases left to review. Skim the word list in")
        print(f"    {review_path}")
        print("once more before sharing - it is the only check for a name no rule knows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
