"""Tests for `scripts/sanitize_statement.py`.

The script has two jobs that pull against each other: remove everything that
identifies the contributor, and preserve everything a parser author needs.
Either one is easy alone - a blank page is perfectly private, and a copy is
perfectly faithful. So the tests come in two halves, and a change that
improves one at the other's expense fails the other half.

The privacy half matters most: a bug here leaks a real person's statement into
a public issue tracker. Those tests assert on the *output file's text* as a
recipient would read it, never on the script's internal bookkeeping.
"""

import glob
import os
import re
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest
from reportlab.pdfgen import canvas

import sanitize_statement as sanitize
from app.parsing.registry import detect_and_parse

UOB_SAMPLE = "../PDF Examples (Sanitized)/UOB/Account Statements/SampleAccountStatement_Feb2024.pdf"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_statement.py"


def _text_of(path) -> str:
    with pdfplumber.open(path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _words_of(path):
    with pdfplumber.open(path) as pdf:
        return [w for page in pdf.pages for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)]


def _run(pdf_path: Path, *args: str) -> Path:
    out = pdf_path.with_name(pdf_path.stem + ".sanitized.pdf")
    assert sanitize.main([str(pdf_path), *args]) == 0
    return out


@pytest.fixture
def statement_with_pii(tmp_path) -> Path:
    """A statement carrying every kind of identifier a real one carries.

    Written out longhand rather than reusing a fixture from `PDF Examples
    (Sanitized)/` because those, by construction, have nothing to redact -
    they would let a script that did nothing at all pass every test here.
    """
    path = tmp_path / "real.pdf"
    c = canvas.Canvas(str(path))
    c.setAuthor("Jane Wong Mei Ling")
    c.setTitle("Statement for Jane Wong Mei Ling")
    rows = [
        (40, "United Overseas Bank Limited"),
        (60, "JANE WONG MEI LING"),
        (72, "88 ORCHID CRESCENT #12-345"),
        (84, "SINGAPORE 546218"),
        (96, "NRIC S8412345J"),
        (108, "Contact 91234567 or jane.wong@example.net"),
        (140, "Statement of Account"),
        (158, "Period: 01 Feb 2024 to 29 Feb 2024"),
        (200, "Account Transaction Details"),
        (216, "One Account 372-901-455-8"),
    ]
    for top, line in rows:
        c.setFont("Helvetica", 9)
        c.drawString(36, 841.89 - top - 7.2, line)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(52.5, 841.89 - 240 - 7.2, "Date")
    c.drawString(120.5, 841.89 - 240 - 7.2, "Description")
    c.drawRightString(386.0, 841.89 - 240 - 7.2, "Withdrawals")
    c.drawRightString(465.5, 841.89 - 240 - 7.2, "Deposits")
    c.drawRightString(545.0, 841.89 - 240 - 7.2, "Balance")

    c.setFont("Helvetica", 9)
    table = [
        ("01 Feb", "BALANCE B/F", None, None, "5,000.00"),
        ("03 Feb", "PAYNOW-FAST To: TAN WEI MING", "120.00", None, "4,880.00"),
        ("05 Feb", "NETS Debit-Consumer COLD STORAGE", "45.20", None, "4,834.80"),
        ("09 Feb", "Inward CR - GIRO PIB0000123456789012", None, "3,200.00", "8,034.80"),
        (None, "Total", "165.20", "3,200.00", "8,034.80"),
    ]
    top = 258.0
    for date, description, withdrawal, deposit, balance in table:
        y = 841.89 - top - 7.2
        if date:
            c.drawString(52.5, y, date)
        c.drawString(120.5, y, description)
        if withdrawal:
            c.drawRightString(386.0, y, withdrawal)
        if deposit:
            c.drawRightString(465.5, y, deposit)
        c.drawRightString(545.0, y, balance)
        top += 12.5
    c.save()
    return path


# --- the privacy half -----------------------------------------------------


def test_identifiers_are_gone_from_the_output(statement_with_pii):
    out = _run(statement_with_pii, "--redact", "JANE WONG MEI LING")
    text = _text_of(out)

    for secret in ("JANE", "WONG", "MEI LING", "S8412345J", "91234567", "jane.wong@example.net", "372-901-455-8", "546218"):
        assert secret not in text, f"{secret!r} survived sanitizing"


def test_the_output_is_a_new_file_not_an_annotated_copy(statement_with_pii):
    """A black box drawn over text leaves the text in the file. This script
    rebuilds instead, so the name must be absent from the raw bytes too - not
    merely absent from what a viewer chooses to render."""
    out = _run(statement_with_pii, "--redact", "JANE WONG MEI LING")
    raw = out.read_bytes()
    assert b"JANE WONG MEI LING" not in raw
    # The name was in the source's PDF metadata as well as its text.
    assert b"Jane Wong Mei Ling" not in raw


def test_counterparty_name_after_a_marker_is_replaced(statement_with_pii):
    out = _run(statement_with_pii, "--redact", "JANE WONG MEI LING")
    text = _text_of(out)
    assert "TAN WEI MING" not in text
    # ...but the rail's own wording survives, or the fixture stops exercising
    # the categorization engine's PayNow handling.
    assert "PAYNOW-FAST" in text


def test_counterparties_can_be_kept_for_manual_review(statement_with_pii):
    out = _run(statement_with_pii, "--keep-counterparties")
    assert "TAN WEI MING" in _text_of(out)


def test_reference_numbers_are_replaced_even_when_prefixed_with_letters(statement_with_pii):
    out = _run(statement_with_pii, "--redact", "JANE WONG MEI LING")
    text = _text_of(out)
    assert "PIB0000123456789012" not in text
    assert re.search(r"PIB\d{16}", text), "the reference should keep its shape, not vanish"


def test_a_reference_number_ends_a_counterparty_run_instead_of_joining_it():
    """A name run that hits a reference number should hand it to the
    identifier rule. Both redact it, but only that rule keeps its shape, and
    the shape is what a parser author needs to see."""
    words = [
        sanitize.Word(text=t, x0=i * 20, x1=i * 20 + 15, top=0, bottom=9, size=9, bold=False)
        for i, t in enumerate(["To:", "TAN", "WEI", "MING", "PIB0000123456789012"])
    ]
    result = sanitize.redact_line(words, [], False, False, sanitize.Stats())
    assert re.fullmatch(r"PIB\d{16}", result[-1].text)
    assert all(w.text.startswith("SAM") for w in result[1:4])


def test_a_single_word_redaction_does_not_strike_words_that_merely_contain_it():
    """Substring matching would make --redact "TAN" gut every merchant with
    those letters in it. What survives is the point of sharing the file."""
    words = [sanitize.Word(text=t, x0=0, x1=10, top=0, bottom=9, size=9, bold=False) for t in ["STANDARD", "TAN", "INSTANT"]]
    hits = sanitize._literal_matches(words, ["TAN"])
    assert hits == {1}


def test_a_multi_word_redaction_matches_the_run_of_words():
    words = [sanitize.Word(text=t, x0=0, x1=10, top=0, bottom=9, size=9, bold=False) for t in ["PAID", "JANE", "WONG", "TODAY"]]
    assert sanitize._literal_matches(words, ["Jane Wong"]) == {1, 2}


def test_the_same_account_number_always_becomes_the_same_placeholder():
    """Statements are shared in batches, and a parser that groups transactions
    by account needs the account to stay one account across them."""
    first = sanitize._pseudonym_digits("372-901-455-8")
    assert first == sanitize._pseudonym_digits("372-901-455-8")
    assert first != sanitize._pseudonym_digits("372-901-455-9")
    assert first != "372-901-455-8"
    assert re.fullmatch(r"\d{3}-\d{3}-\d{3}-\d", first), "the placeholder should keep the original's shape"


def test_verification_reports_text_that_should_have_been_removed(tmp_path):
    """The script re-reads its own output rather than trusting its rules. This
    is that check failing as it should."""
    leaky = tmp_path / "leaky.pdf"
    c = canvas.Canvas(str(leaky))
    c.drawString(36, 800, "JANE WONG and S8412345J")
    c.save()
    problems = sanitize.verify(leaky, ["JANE WONG"])
    assert any("JANE WONG" in p for p in problems)
    assert any("NRIC" in p for p in problems)


def test_the_review_file_lists_what_survived(statement_with_pii):
    """No rule can know a contributor's landlord's name. The review list is
    how they find it, so it has to actually enumerate what's left."""
    out = _run(statement_with_pii, "--redact", "JANE WONG MEI LING")
    review = out.with_suffix(".review.txt").read_text()
    assert "COLD" in review and "STORAGE" in review
    assert "JANE" not in review
    assert "--redact" in review, "the review file should say how to act on what it lists"


# --- the fidelity half ----------------------------------------------------


def test_a_sanitized_statement_still_parses_to_the_same_figures(tmp_path):
    """The whole point. Amounts, dates and running balances have to come back
    identical, or the shared file can't be used to test a parser."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    out = _run(source, "--redact", "SAMPLE CUSTOMER")

    with pdfplumber.open(UOB_SAMPLE) as pdf:
        before = detect_and_parse(pdf.pages).accounts[0]
    with pdfplumber.open(out) as pdf:
        after = detect_and_parse(pdf.pages).accounts[0]

    assert len(after.transactions) == len(before.transactions)
    assert [t.amount for t in after.transactions] == [t.amount for t in before.transactions]
    assert [t.transaction_date for t in after.transactions] == [t.transaction_date for t in before.transactions]
    assert [t.balance for t in after.transactions] == [t.balance for t in before.transactions]
    # The account number is the one thing that must NOT survive.
    assert after.account_number != before.account_number
    assert after.account_type == before.account_type


def test_word_geometry_is_preserved(tmp_path):
    """The parsers locate columns by x-position and rows by y-position, so a
    faithful copy means the boxes land where they did - not just that the same
    text is somewhere on the page."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    out = _run(source, "--redact", "SAMPLE CUSTOMER")

    before = _words_of(UOB_SAMPLE)
    after = _words_of(out)
    assert len(after) == len(before), "the output should re-read as the same number of words"

    for original, rebuilt in zip(before, after):
        assert abs(rebuilt["x0"] - original["x0"]) < 0.5
        assert abs(rebuilt["x1"] - original["x1"]) < 0.5
        assert abs(rebuilt["top"] - original["top"]) < 0.5


def test_amounts_survive_by_default_and_can_be_removed_on_request(statement_with_pii):
    kept = _text_of(_run(statement_with_pii, "--redact", "JANE WONG MEI LING"))
    assert "3,200.00" in kept

    stripped = _text_of(_run(statement_with_pii, "--redact", "JANE WONG MEI LING", "--redact-amounts"))
    assert "3,200.00" not in stripped
    assert "0,000.00" in stripped, "an amount should become a placeholder, not disappear"


@pytest.mark.parametrize("token", ["01", "Feb", "2024", "29", "15/03", "15-03-2024", "2024-03-15"])
def test_dates_survive_sanitizing(token):
    """Asserted on the redaction result rather than on a predicate, because
    what matters is that the date comes out the other side unchanged - which
    rule spared it is an implementation detail."""
    word = sanitize.Word(text=token, x0=0, x1=20, top=0, bottom=9, size=9, bold=False)
    (result,) = sanitize.redact_line([word], [], False, False, sanitize.Stats())
    assert result.text == token


def test_amounts_are_never_mistaken_for_identifiers():
    for amount in ("1,234.56", "0.99", "123456.78", "1,234.56CR", "(45.00)"):
        assert sanitize.is_money(amount), f"{amount!r} would be redacted as an identifier"


# --- --structure-only: the strongest privacy tier ------------------------

COMMITTED_FIXTURES = sorted(glob.glob("../PDF Examples (Sanitized)/*/*/*.pdf"))


@pytest.mark.parametrize("fixture", COMMITTED_FIXTURES, ids=lambda p: os.path.basename(p))
def test_structure_only_costs_the_parsers_nothing(fixture, tmp_path):
    """The claim --structure-only rests on: a parser reads the statement's own
    chrome - the bank name, the column headings, the BALANCE B/F and Total
    rows, the statement date - and never reads a transaction description for
    anything but passing it through.

    So throwing every description away wholesale should leave the parse
    bit-for-bit unchanged. If this ever fails, some parser has quietly grown a
    dependency on customer wording, and the mode's whole justification with it.
    """
    source = tmp_path / os.path.basename(fixture)
    source.write_bytes(Path(fixture).read_bytes())
    out = _run(source, "--structure-only")

    with pdfplumber.open(fixture) as pdf:
        before = detect_and_parse(pdf.pages)
    with pdfplumber.open(out) as pdf:
        after = detect_and_parse(pdf.pages)

    assert len(after.accounts) == len(before.accounts)
    for original, rebuilt in zip(before.accounts, after.accounts):
        assert [t.transaction_date for t in rebuilt.transactions] == [t.transaction_date for t in original.transactions]
        assert [t.amount for t in rebuilt.transactions] == [t.amount for t in original.transactions]
        assert [t.balance for t in rebuilt.transactions] == [t.balance for t in original.transactions]


def test_structure_only_keeps_the_banks_wording_and_destroys_the_customers(tmp_path):
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    text = _text_of(_run(source, "--structure-only"))

    # The template survives, or nothing can find the table.
    for chrome in ("United Overseas Bank", "Statement of Account", "Description", "Withdrawals", "BALANCE B/F", "Total"):
        assert chrome in text, f"{chrome!r} is chrome and must survive"
    # The descriptions do not.
    for content in ("SAMPLE MART", "SAMPLE PAYEE", "SAMPLE EMPLOYER", "SAMPLE ONLINE STORE"):
        assert content not in text, f"{content!r} is customer content and must not survive"
    # Figures and dates still do, so the sample still reconciles.
    assert "5,000.00" in text
    assert "01 Feb" in text


def test_structure_only_can_be_told_to_keep_wording_it_does_not_recognize(tmp_path):
    """No built-in vocabulary knows every bank's headings. The failure mode is
    a sample that won't parse, not a leak - and --keep is the fix."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    assert "SAMPLE MART" not in _text_of(_run(source, "--structure-only"))
    assert "SAMPLE MART" in _text_of(_run(source, "--structure-only", "--keep", "SAMPLE MART"))


# --- the command line -----------------------------------------------------


def test_runs_as_a_script_from_a_clone(tmp_path):
    """A contributor runs this straight from a checkout, so it has to work
    without the package being importable the way the tests import it."""
    source = tmp_path / "uob.pdf"
    source.write_bytes(Path(UOB_SAMPLE).read_bytes())
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--redact", "SAMPLE CUSTOMER", "--check-parse"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "checks passed" in result.stdout
    assert "parses as UOB" in result.stdout


def test_the_console_output_never_reads_as_an_all_clear(statement_with_pii):
    """The checks confirm the rules did what they were asked. They say nothing
    about a name no rule was going to recognize, and an earlier version of this
    line read as "no PII found" while five names sat in the output. Anything
    that sounds like a clean bill of health here gets people to skip the review
    file, which is the only thing that catches those."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(statement_with_pii), "--redact", "JANE WONG MEI LING"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    lowered = result.stdout.lower()
    for phrase in ("no pii", "safe to share", "all clear", "no personal"):
        assert phrase not in lowered
    assert "review" in lowered, "the output must point at the review file"
