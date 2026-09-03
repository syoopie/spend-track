"""Tests for `scripts/sanitize_statement.py`.

The script has two jobs that pull against each other: remove everything that
identifies the contributor, and preserve everything a parser author needs.
Either one is easy alone - a blank page is perfectly private, a copy is
perfectly faithful - so the tests come in two halves, and a change that
improves one at the other's expense fails the other half.

The privacy half asserts on the *bytes of the output file*, as a recipient
would read it, never on the script's internal bookkeeping. Its fixture carries
every shape of personal data a real statement carries - names written six ways,
identifiers split and joined and prefixed, PII on a later page, PII in the
file's metadata - and each shape is its own parametrized case, so a regression
names the shape that broke rather than "a leak happened somewhere".

Several of these pin bugs that a plain reading of the code did not reveal, and
are worth keeping for that reason alone: identifiers split across words, a bare
four-digit year, and a reference number with a letter prefix.
"""

import glob
import os
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest
from reportlab.pdfgen import canvas

import sanitize_statement as sanitize
from app.parsing.registry import detect_and_parse

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_statement.py"
COMMITTED_FIXTURES = sorted(glob.glob("../PDF Examples (Sanitized)/*/*/*.pdf"))
UOB_SAMPLE = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"

#: (case name, the line drawn on page 1, the text that must not survive).
PII_CASES = [
    ("name in the address block", "JANE WONG MEI LING", "JANE WONG MEI LING"),
    ("name, hyphenated", "Contact: Anne-Marie Tan-Wong", "Anne-Marie"),
    ("name, apostrophe", "Held by Siobhan O'Brien", "O'Brien"),
    ("street address", "88 ORCHID CRESCENT #12-345", "ORCHID CRESCENT"),
    ("postal code", "SINGAPORE 546218", "546218"),
    ("NRIC", "NRIC S8412345J", "S8412345J"),
    ("email", "Email jane.wong@example.net", "jane.wong@example.net"),
    ("phone", "Tel 91234567", "91234567"),
    ("phone, spaced", "Tel 9123 4567", "9123 4567"),
    ("phone, country code", "Mobile +65 9187 6543", "9187 6543"),
    ("account number, grouped", "Account No. 372-901-455-8", "372-901-455-8"),
    ("account number, flat", "A/C 0123456789", "0123456789"),
    ("card number, spaced", "Card 4111 1111 1111 1234", "4111 1111 1111 1234"),
    ("card number, dashed", "Card 4222-2222-2222-4321", "4222-2222-2222-4321"),
    ("reference, letter prefix", "Ref PIB0000123456789012", "PIB0000123456789012"),
    ("UEN", "UEN 201812345K", "201812345K"),
    ("counterparty", "PAYNOW To: TAN WEI MING", "TAN WEI MING"),
    ("name after an honorific", "GIRO Payment MRS LIM SIEW KHENG", "LIM SIEW KHENG"),
]

#: PII on a later page, to catch a first-page-only rule.
PAGE_TWO_CASES = [
    ("name on a later page", "Joint account holder KAMALA DEVI", "KAMALA DEVI"),
    ("card number on a later page", "Secondary card 5500 0000 0000 9876", "5500 0000 0000 9876"),
]

#: Figures and dates that must come through untouched. Every leak assertion is
#: paired against these: a sanitizer that removes the amounts is perfectly
#: private and perfectly useless.
MUST_SURVIVE = ["01 Feb", "15/03/2024", "1,234.56", "3,200.00", "123456.78"]


def _build_statement(path: Path) -> None:
    c = canvas.Canvas(str(path))
    # PII in metadata as well as content - a viewer never shows this, and a
    # tool that edits rather than rebuilds leaves it in place.
    c.setAuthor("Jane Wong Mei Ling")
    c.setTitle("Statement for Jane Wong Mei Ling")
    c.setSubject("Account 372-901-455-8")

    c.setFont("Helvetica", 9)
    top = 40.0
    for _name, line, _secret in PII_CASES:
        c.drawString(36, 841.89 - top - 7.2, line)
        top += 14
    for keep in MUST_SURVIVE:
        c.drawString(380, 841.89 - top - 7.2, keep)
        top += 14
    c.showPage()

    c.setFont("Helvetica", 9)
    top = 60.0
    for _name, line, _secret in PAGE_TWO_CASES:
        c.drawString(36, 841.89 - top - 7.2, line)
        top += 14
    c.save()


def _text_of(path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _run(pdf_path: Path, *args: str) -> Path:
    assert sanitize.main([str(pdf_path), *args]) == 0
    return pdf_path.with_name(pdf_path.stem + ".sanitized.pdf")


def _words(texts: list[str]) -> list[sanitize.Word]:
    """Words laid out the way a PDF prints one grouped number: a space apart."""
    words, x = [], 100.0
    for token in texts:
        width = len(token) * 5.0
        words.append(sanitize.Word(text=token, x0=x, x1=x + width, top=0, bottom=9, size=9, bold=False))
        x += width + 2.5
    return words


@pytest.fixture(scope="module")
def sanitized(tmp_path_factory):
    """Sanitized with no --redact at all - the point of default-deny being
    that it needs none. Sanitize once, assert many times."""
    source = tmp_path_factory.mktemp("leaks") / "statement.pdf"
    _build_statement(source)
    out = _run(source)
    with pdfplumber.open(out) as pdf:
        text = " ".join(" ".join((page.extract_text() or "").split()) for page in pdf.pages)
    return {"text": text, "raw": out.read_bytes(), "review": out.with_suffix(".review.txt").read_text()}


# --- the privacy half -----------------------------------------------------


@pytest.mark.parametrize(
    ("case", "secret"),
    [(name, secret) for name, _line, secret in PII_CASES + PAGE_TWO_CASES],
    ids=[name for name, _line, _secret in PII_CASES + PAGE_TWO_CASES],
)
def test_no_pii_shape_survives(sanitized, case, secret):
    assert secret not in sanitized["text"], f"{case}: {secret!r} is readable in the output"
    assert secret.encode() not in sanitized["raw"], f"{case}: {secret!r} is in the output's bytes"


def test_metadata_pii_does_not_survive(sanitized):
    """A black box drawn over text leaves the text in the file, and leaves the
    metadata untouched entirely. This rebuilds instead."""
    for secret in (b"Jane Wong Mei Ling", b"Statement for Jane", b"372-901-455-8"):
        assert secret not in sanitized["raw"]


def test_the_verifier_refuses_a_file_with_an_unaccounted_word(tmp_path):
    """Default-deny makes verification exhaustive rather than heuristic: a word
    that is not template, a date, a figure or something this script wrote has
    no business being in a finished file, whatever it looks like."""
    leaky = tmp_path / "leaky.pdf"
    c = canvas.Canvas(str(leaky))
    c.drawString(36, 800, "BALANCE Kamala 1,234.56")
    c.save()
    problems = sanitize.verify(leaky.read_bytes(), frozenset(), [], "leaky.pdf", written=set())
    assert any("Kamala" in p for p in problems)
    # ...and does not cry wolf over the template word or the figure beside it.
    assert not any("BALANCE" in p or "1,234.56" in p for p in problems)


def test_a_file_name_carrying_the_contributors_name_fails_verification(tmp_path):
    """The file name travels with the file. "JaneWong-Jan2024.pdf" identifies
    its owner as well as anything inside it does."""
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _build_statement(source)
    assert sanitize.main([str(source), "--redact", "Jane Wong"]) == 1

    out = tmp_path / "sample-uob-account.pdf"
    assert sanitize.main([str(source), "--redact", "Jane Wong", "--output", str(out)]) == 0


def test_the_process_exits_non_zero_when_a_check_fails(tmp_path):
    """The exit code is what a contributor's shell, and any wrapper, reads."""
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _build_statement(source)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--redact", "Jane Wong"], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert "do not share this file" in result.stdout


@pytest.mark.parametrize(
    ("tokens", "digits"),
    [(["4111", "1111", "1111", "1234"], 16), (["9123", "4567"], 8), (["+65", "9123", "4567"], 10)],
)
def test_identifiers_split_across_words_are_replaced(tokens, digits):
    """A statement printing an identifier in groups defeats any per-word digit
    threshold, because no single group reaches it. Common, and invisible."""
    result = sanitize.redact_line(_words(tokens))
    assert [w.text for w in result] != tokens
    assert [len(w.text) for w in result] == [len(t) for t in tokens], "each group keeps its width"
    assert sum(c.isdigit() for w in result for c in w.text) == digits


def test_a_letter_prefixed_reference_has_its_digits_replaced_too():
    """Shaping alone maps only letters, so "PIB0000123456789012" came out as
    "XXX0000123456789012" - the whole reference intact behind a masked prefix."""
    (result,) = sanitize.redact_line(_words(["PIB0000123456789012"]))
    assert "0000123456789012" not in result.text
    assert result.text.startswith("XXX")


def test_a_name_that_is_also_a_template_word_can_be_named_explicitly():
    """The one case default-deny cannot cover on its own: somebody called May,
    a merchant called Trust. is_chrome keeps them, so --redact must remove them."""
    assert sanitize.redact_line(_words(["May", "Lim"]))[0].text == "May"
    assert sanitize.redact_line(_words(["May", "Lim"]), ["May Lim"])[0].text != "May"


@pytest.mark.parametrize("printed,typed", [(["Anne", "Marie"], "Anne-Marie"), (["Anne-Marie"], "Anne Marie")])
def test_redact_matches_however_the_statement_split_the_name(printed, typed):
    """A contributor types their name the way they know it, and cannot be
    expected to guess how the PDF broke it into words."""
    assert sanitize._literal_matches(_words(printed), [typed]) == set(range(len(printed)))


@pytest.mark.parametrize("word", ["STANDARD", "INSTANT", "TANGERINE"])
def test_redact_never_matches_a_substring(word):
    """Substring matching would make --redact "TAN" gut every merchant with
    those letters in it. Over-redaction is not free - what survives is the
    entire reason to share the file."""
    assert sanitize._literal_matches(_words([word]), ["TAN"]) == set()


# --- the fidelity half ----------------------------------------------------


@pytest.mark.parametrize("fixture", COMMITTED_FIXTURES, ids=lambda p: os.path.basename(p))
def test_sanitizing_costs_the_parsers_nothing(fixture, tmp_path):
    """The claim the whole design rests on: a parser reads the statement's own
    chrome - the bank name, the column headings, the BALANCE B/F and Total
    rows, the statement date - and never reads a description for anything but
    passing it through.

    So throwing every description away should leave the parse bit-for-bit
    unchanged. If this fails, a parser has grown a dependency on customer
    wording and the justification for discarding it is gone.
    """
    source = tmp_path / os.path.basename(fixture)
    source.write_bytes(Path(fixture).read_bytes())
    out = _run(source)

    with pdfplumber.open(fixture) as pdf:
        before = detect_and_parse(pdf.pages)
    with pdfplumber.open(out) as pdf:
        after = detect_and_parse(pdf.pages)

    assert len(after.accounts) == len(before.accounts)
    for original, rebuilt in zip(before.accounts, after.accounts):
        assert [t.transaction_date for t in rebuilt.transactions] == [t.transaction_date for t in original.transactions]
        assert [t.amount for t in rebuilt.transactions] == [t.amount for t in original.transactions]
        assert [t.balance for t in rebuilt.transactions] == [t.balance for t in original.transactions]


def test_word_geometry_is_preserved(tmp_path):
    """The parsers locate columns by x-position and rows by y-position, so a
    faithful copy means the boxes land where they did - not just that something
    is somewhere on the page."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    out = _run(source)

    def boxes(path):
        with pdfplumber.open(path) as pdf:
            return [w for page in pdf.pages for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)]

    before, after = boxes(UOB_SAMPLE), boxes(out)
    assert len(after) == len(before), "the output should re-read as the same number of words"
    for original, rebuilt in zip(before, after):
        assert abs(rebuilt["x0"] - original["x0"]) < 0.5
        assert abs(rebuilt["x1"] - original["x1"]) < 0.5
        assert abs(rebuilt["top"] - original["top"]) < 0.5


def test_the_banks_wording_survives_and_the_customers_does_not(tmp_path):
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    text = _text_of(_run(source))

    for chrome in ("United Overseas Bank", "Statement of Account", "Description", "Withdrawals", "BALANCE B/F", "Total"):
        assert chrome in text, f"{chrome!r} is template and must survive"
    for content in ("SAMPLE MART", "SAMPLE PAYEE", "SAMPLE EMPLOYER"):
        assert content not in text, f"{content!r} is customer content and must not survive"


@pytest.mark.parametrize("keep", MUST_SURVIVE)
def test_figures_and_dates_are_not_collateral_damage(sanitized, keep):
    assert keep in sanitized["text"]


def test_a_bare_year_is_kept():
    """A four-digit year is a bare digit run with no separators, and every
    digit-bearing word is replaced with no length threshold. Left unguarded
    that moved every transaction in the fixture set to the year 6557 -
    silently, since the dates still looked like dates."""
    assert sanitize.redact_line(_words(["2024"]))[0].text == "2024"
    # ...but a four-digit card group is not a year and must still go.
    assert sanitize.redact_line(_words(["4111"]))[0].text != "4111"


def test_amounts_can_be_removed_on_request(tmp_path):
    source = tmp_path / "real.pdf"
    _build_statement(source)
    assert "3,200.00" in _text_of(_run(source))
    stripped = _text_of(_run(source, "--redact-amounts"))
    assert "3,200.00" not in stripped
    assert "0,000.00" in stripped, "an amount should become a placeholder, not disappear"


def test_wording_the_script_does_not_recognize_can_be_kept(tmp_path):
    """No built-in vocabulary knows every bank's headings. The failure mode is
    a sample that won't parse, not a leak - and --keep is the fix."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    assert "SAMPLE MART" not in _text_of(_run(source))
    assert "SAMPLE MART" in _text_of(_run(source, "--keep", "SAMPLE MART"))


def test_the_review_file_lists_what_was_kept(sanitized):
    """Short by construction, because everything not recognized was replaced
    rather than judged - so it is a list a human will actually read."""
    assert "BALANCE" in sanitized["review"] or "Account" in sanitized["review"]
    assert "KAMALA" not in sanitized["review"]


def test_runs_as_a_script_from_a_clone(tmp_path):
    """A contributor runs this straight from a checkout, so it has to work
    without the package being importable the way these tests import it."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--check-parse"], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "parses as UOB" in result.stdout
    # Never phrased as an all-clear: the checks confirm the rules did what they
    # were asked, and an earlier version read as "no PII found" over five names.
    for phrase in ("no pii", "safe to share", "all clear"):
        assert phrase not in result.stdout.lower()
