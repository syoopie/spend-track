"""Adversarial leak tests for `scripts/sanitize_statement.py`.

`test_sanitize_statement.py` tests the rules. This file tries to beat them.

It builds one statement carrying every shape of personal data a real statement
carries - names written six ways, identifiers split and joined and prefixed,
PII on a later page, PII in the file's metadata - sanitizes it, and asserts on
the *bytes of the output file* that nothing got through.

Every case here is written as its own parametrized entry rather than as one big
assertion, so a regression names the exact shape that broke rather than "a leak
happened somewhere".

The first run of this hunt found ten leaks in code that had passed twenty-two
tests, and the three that mattered most are pinned below by name:

* `card number, spaced` and `phone, spaced` - a statement printing an
  identifier in groups ("4111 1111 1111 1234") defeats any per-word digit
  threshold, because no single group reaches it. Common, invisible, total.
* `name after an honorific` - "GIRO Payment MRS LIM SIEW KHENG" has no
  transfer preposition for the counterparty rule to key on.
* `the same name on two pages` - the rules are line-scoped, so a name caught
  after a "To:" on one line and printed bare on another was removed once and
  missed once.
"""

import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest
from reportlab.pdfgen import canvas

import sanitize_statement as sanitize

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sanitize_statement.py"

#: (case name, line drawn on page 1, the text that must not survive).
#: The secret is checked against the output's text *and* its raw bytes.
PII_CASES = [
    ("name in the address block", "JANE WONG MEI LING", "JANE WONG MEI LING"),
    ("name, hyphenated", "Contact: Anne-Marie Tan-Wong", "Anne-Marie"),
    ("name, apostrophe", "Held by Siobhan O'Brien", "O'Brien"),
    ("name, three parts", "Joint holder Jose Ramirez Nunez", "Ramirez"),
    ("street address", "88 ORCHID CRESCENT #12-345", "ORCHID CRESCENT"),
    ("postal code", "SINGAPORE 546218", "546218"),
    ("NRIC", "NRIC S8412345J", "S8412345J"),
    ("NRIC, lower case", "nric s8412345j", "s8412345j"),
    ("FIN", "FIN G1234567X", "G1234567X"),
    ("email", "Email jane.wong@example.net", "jane.wong@example.net"),
    ("phone", "Tel 91234567", "91234567"),
    ("phone, spaced", "Tel 9123 4567", "9123 4567"),
    ("phone, country code", "Mobile +65 9187 6543", "9187 6543"),
    ("account number, grouped", "Account No. 372-901-455-8", "372-901-455-8"),
    ("account number, spaced", "Account 372 901455 8", "372 901455 8"),
    ("account number, flat", "A/C 0123456789", "0123456789"),
    ("card number, spaced", "Card 4111 1111 1111 1234", "4111 1111 1111 1234"),
    ("card number, dashed", "Card 4222-2222-2222-4321", "4222-2222-2222-4321"),
    ("reference, letter prefix", "Ref PIB0000123456789012", "PIB0000123456789012"),
    ("UEN", "UEN 201812345K", "201812345K"),
    ("counterparty after To:", "PAYNOW To: TAN WEI MING", "TAN WEI MING"),
    ("counterparty, lower case to", "FAST PAYMENT to Adrian Lee OTHR", "Adrian Lee"),
    ("name after an honorific", "GIRO Payment MRS LIM SIEW KHENG", "LIM SIEW KHENG"),
    ("name inside a description", "TRANSFER FROM JANE WONG SAVINGS", "JANE WONG"),
]

#: PII that only appears on page two, to catch a first-page-only rule.
PAGE_TWO_CASES = [
    ("name on a later page", "Joint account holder KAMALA DEVI", "KAMALA DEVI"),
    ("card number on a later page", "Secondary card 5500 0000 0000 9876", "5500 0000 0000 9876"),
]

#: The same name printed twice, once where a rule catches it and once bare.
#: Only a whole-document check notices the second one.
REPEATED_NAME = "TAN WEI MING"

#: Figures and dates that must come through untouched - a sanitizer that
#: destroys these is useless for its actual purpose, so every leak assertion
#: is paired against these.
MUST_SURVIVE = ["01 Feb", "15/03/2024", "1,234.56", "3,200.00", "12.40", "123456.78", "COLD STORAGE"]

#: Everything a contributor would realistically pass, given the review file
#: correctly surfaces the bare names (asserted separately below).
REDACTIONS = [
    "JANE WONG MEI LING",
    "Anne-Marie Tan-Wong",
    "Siobhan O'Brien",
    "Jose Ramirez Nunez",
    "ORCHID CRESCENT",
    "KAMALA DEVI",
    REPEATED_NAME,  # flagged by the review file for its bare second occurrence
]


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
    # The repeat: caught by the counterparty rule on page 1, bare here.
    c.drawString(36, 841.89 - top - 7.2, f"Standing instruction {REPEATED_NAME} monthly")
    c.save()


@pytest.fixture(scope="module")
def sanitized(tmp_path_factory):
    """Sanitize once, assert many times - the run is the expensive part."""
    directory = tmp_path_factory.mktemp("leaks")
    source = directory / "statement.pdf"
    _build_statement(source)

    args = [str(source)]
    for literal in REDACTIONS:
        args += ["--redact", literal]
    assert sanitize.main(args) == 0

    out = source.with_name("statement.sanitized.pdf")
    with pdfplumber.open(out) as pdf:
        text = " ".join(" ".join((page.extract_text() or "").split()) for page in pdf.pages)
    return {
        "path": out,
        "text": text,
        "raw": out.read_bytes(),
        "review": out.with_suffix(".review.txt").read_text(encoding="utf-8"),
    }


@pytest.mark.parametrize(
    ("case", "secret"),
    [(name, secret) for name, _line, secret in PII_CASES + PAGE_TWO_CASES],
    ids=[name for name, _line, _secret in PII_CASES + PAGE_TWO_CASES],
)
def test_no_pii_shape_survives_sanitizing(sanitized, case, secret):
    assert secret not in sanitized["text"], f"{case}: {secret!r} is readable in the output"
    assert secret.encode() not in sanitized["raw"], f"{case}: {secret!r} is in the output's bytes"


def test_a_name_removed_on_one_line_is_removed_on_every_line(sanitized):
    """The rules are line-scoped. This name is introduced by "To:" on page one
    and printed bare on page two, so the per-line rules catch one and miss the
    other - which is what the whole-document cross-check exists for."""
    assert REPEATED_NAME not in sanitized["text"]
    assert REPEATED_NAME.encode() not in sanitized["raw"]


def test_a_half_removed_name_fails_verification_rather_than_shipping(tmp_path):
    """The case above, with the contributor *not* having redacted the name: the
    rules remove it after the "To:" on page one and leave the bare page-two
    copy standing. Nothing per-line can see that, so the run has to fail on the
    whole-document comparison instead of writing a file that looks finished.

    This is the test that fails if CROSS_CHECK_MIN_LETTERS is ever raised to
    something that looks more sensible in the abstract: every part of
    "TAN WEI MING" is three characters or fewer."""
    source = tmp_path / "half.pdf"
    _build_statement(source)
    assert sanitize.main([str(source), "--redact", "JANE WONG MEI LING"]) == 1


def test_metadata_pii_does_not_survive(sanitized):
    for secret in ("Jane Wong Mei Ling", "Statement for Jane", "372-901-455-8"):
        assert secret.encode() not in sanitized["raw"], f"{secret!r} survived in metadata"


@pytest.mark.parametrize("keep", MUST_SURVIVE)
def test_figures_and_dates_are_not_collateral_damage(sanitized, keep):
    """Every leak fix is paired with this. A sanitizer that removes the amounts
    is perfectly private and perfectly useless."""
    assert keep in sanitized["text"]


def test_the_review_file_names_every_bare_name_it_could_not_remove():
    """The bare names are not machine-findable, so the review file is the only
    thing standing between them and a public issue tracker. It has to surface
    all of them, and it has to be short enough to actually get read."""
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "statement.pdf"
        _build_statement(source)
        # Only the contributor's own name given - the rest must be surfaced.
        # The run itself fails (the cross-check catches the half-removed
        # "TAN WEI MING", which has its own test); the review file is written
        # before verification precisely so it is there to act on when it does.
        sanitize.main([str(source), "--redact", "JANE WONG MEI LING"])
        review = source.with_name("statement.sanitized.review.txt").read_text(encoding="utf-8")

    candidates = review.split("CHECK THESE FIRST")[1].split("EVERYTHING ELSE")[0]
    for expected in ("Anne-Marie", "O'Brien", "Ramirez", "ORCHID CRESCENT", "KAMALA DEVI"):
        assert expected in candidates, f"the review file failed to flag {expected!r}"
    # Short enough to read. The flat word list this replaced ran to 72 entries
    # with the names scattered through it, which is not a review, it's a haystack.
    assert len([ln for ln in candidates.splitlines() if ln.startswith("  ") and not ln.startswith("      on:")]) <= 12


def test_the_review_loop_terminates(sanitized):
    """The workflow only works if it converges: read the review file, redact
    what it flagged, and what remains is nothing that needs a decision.

    "Nothing" here means no *person*, not an empty list - the candidate list
    catches merchant names too, on purpose, because no rule can tell "COLD
    STORAGE" from "SIEW KHENG" and the one that guessed would be the one that
    dropped a name. A contributor skims and keeps them; the test's job is to
    pin that nothing else is left to skim."""
    candidates = sanitized["review"].split("CHECK THESE FIRST")[1].split("EVERYTHING ELSE")[0]
    listed = [ln.strip() for ln in candidates.splitlines() if ln.startswith("  ") and not ln.startswith("      on:")]
    assert listed == ["COLD STORAGE"], f"expected only the merchant to remain, got {listed}"


def test_sanitizing_an_already_sanitized_file_changes_nothing_further(sanitized, tmp_path):
    """Idempotence. A contributor who runs it twice should not get a second,
    differently-mangled file - and a placeholder must never be mistaken for
    fresh PII and pseudonymised again."""
    again = tmp_path / "again.pdf"
    again.write_bytes(sanitized["raw"])
    assert sanitize.main([str(again)]) == 0
    with pdfplumber.open(again.with_name("again.sanitized.pdf")) as pdf:
        text = " ".join(" ".join((page.extract_text() or "").split()) for page in pdf.pages)
    for keep in MUST_SURVIVE:
        assert keep in text
    assert sanitize.NRIC_PLACEHOLDER in text, "the NRIC placeholder should be left alone, not re-redacted"


def test_a_file_name_carrying_the_contributors_name_fails_verification(tmp_path):
    """The file name travels with the file. "JaneWong-Jan2024.pdf" identifies
    its owner as well as anything inside it does, and attaching it to an issue
    publishes it."""
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _build_statement(source)
    args = [str(source)]
    for literal in REDACTIONS:
        args += ["--redact", literal]
    problems = _problems_from(args)
    assert any("file name" in p for p in problems), problems


def test_naming_the_output_explicitly_resolves_the_file_name_problem(tmp_path):
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _build_statement(source)
    out = tmp_path / "sample-uob-account.pdf"
    args = [str(source), "--output", str(out)]
    for literal in REDACTIONS:
        args += ["--redact", literal]
    assert sanitize.main(args) == 0
    assert out.exists()


def _problems_from(args: list[str]) -> list[str]:
    """Run the script and return the verification problems it printed."""
    import contextlib
    import io as _io

    buffer = _io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = sanitize.main(args)
    output = buffer.getvalue()
    if code == 0:
        return []
    return [ln.strip(" -") for ln in output.splitlines() if ln.startswith("  - ")]


def test_the_process_exits_non_zero_when_a_check_fails(tmp_path):
    """The exit code is what a contributor's shell, and any wrapper script,
    actually reads."""
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _build_statement(source)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), "--redact", "Jane Wong"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "do not share this file" in result.stdout


# --- --structure-only, the mode that needs no judgement calls --------------


@pytest.fixture(scope="module")
def structure_only(tmp_path_factory):
    """Sanitized with --structure-only and *no --redact at all* - the whole
    point of the mode being that it needs none."""
    directory = tmp_path_factory.mktemp("structure")
    source = directory / "statement.pdf"
    _build_statement(source)
    assert sanitize.main([str(source), "--structure-only"]) == 0

    out = source.with_name("statement.sanitized.pdf")
    with pdfplumber.open(out) as pdf:
        text = " ".join(" ".join((page.extract_text() or "").split()) for page in pdf.pages)
    return {"text": text, "raw": out.read_bytes()}


@pytest.mark.parametrize(
    ("case", "secret"),
    [(name, secret) for name, _line, secret in PII_CASES + PAGE_TWO_CASES] + [("repeated name", REPEATED_NAME)],
    ids=[name for name, _line, _secret in PII_CASES + PAGE_TWO_CASES] + ["repeated name"],
)
def test_structure_only_removes_every_shape_with_no_redact_arguments(structure_only, case, secret):
    """The default mode leaves bare names to a human, because no rule can tell
    a landlord from a merchant. --structure-only removes that judgement call
    entirely by keeping only what it positively recognizes as the bank's own
    template - so every one of these goes without being named."""
    assert secret not in structure_only["text"], f"{case}: {secret!r} readable in the output"
    assert secret.encode() not in structure_only["raw"], f"{case}: {secret!r} in the output's bytes"


def test_structure_only_leaves_no_name_shaped_phrase_for_a_human_to_judge(structure_only):
    for fragment in ("ORCHID", "KAMALA", "Ramirez", "Siobhan", "Anne", "Marie"):
        assert fragment not in structure_only["text"]


@pytest.mark.parametrize("keep", ["01 Feb", "15/03/2024", "1,234.56", "3,200.00", "123456.78"])
def test_structure_only_still_keeps_the_figures_and_dates(structure_only, keep):
    """Same pairing as everywhere else: privacy bought by destroying the
    numbers would leave nothing worth sharing."""
    assert keep in structure_only["text"]


def test_structure_only_keeps_a_bare_year_intact():
    """A four-digit year is a bare digit run with no separators, and the mode
    replaces digit-bearing tokens with no length threshold at all. Left
    unguarded that moved every transaction in the fixture set to the year
    6557 - silently, since the dates still looked like dates."""
    word = sanitize.Word(text="2024", x0=0, x1=20, top=0, bottom=9, size=9, bold=False)
    (result,) = sanitize.redact_line([word], [], False, False, sanitize.Stats(), structure_only=True)
    assert result.text == "2024"
    # ...but a four-digit card group is not a year and must still go.
    group = sanitize.Word(text="4111", x0=0, x1=20, top=0, bottom=9, size=9, bold=False)
    (replaced,) = sanitize.redact_line([group], [], False, False, sanitize.Stats(), structure_only=True)
    assert replaced.text != "4111"


def test_structure_only_scrubs_the_digits_of_a_letter_prefixed_reference():
    """Shaping alone maps letters and leaves digits, so "PIB0000123456789012"
    came out as "XXX0000123456789012" - the entire reference intact behind a
    masked prefix."""
    word = sanitize.Word(text="PIB0000123456789012", x0=0, x1=90, top=0, bottom=9, size=9, bold=False)
    (result,) = sanitize.redact_line([word], [], False, False, sanitize.Stats(), structure_only=True)
    assert "0000123456789012" not in result.text
    assert result.text.startswith("XXX")


# --- the rules that fix the split-identifier leak, unit-tested -------------


@pytest.mark.parametrize(
    ("tokens", "expected_digits"),
    [
        (["4111", "1111", "1111", "1234"], 16),
        (["9123", "4567"], 8),
        (["+65", "9123", "4567"], 10),
        (["372", "901455", "8"], 10),
    ],
)
def test_identifiers_split_across_words_are_pseudonymised_as_one(tokens, expected_digits):
    words = _spaced_words(tokens)
    result = sanitize.redact_line(words, [], False, False, sanitize.Stats())
    assert [w.text for w in result] != tokens, "the run should have been replaced"
    assert [len(w.text) for w in result] == [len(t) for t in tokens], "each group should keep its width"
    assert sum(c.isdigit() for w in result for c in w.text) == expected_digits


def test_one_number_pseudonymises_the_same_however_the_statement_groups_it():
    """A card number spaced on one statement and dashed on another is one card,
    and a parser grouping by account has to still see one account."""
    spaced = sanitize.redact_line(_spaced_words(["4111", "1111", "1111", "1234"]), [], False, False, sanitize.Stats())
    joined = "".join(w.text for w in spaced)
    assert joined == sanitize._pseudonym_digits("4111111111111234")
    assert joined == sanitize._pseudonym_digits("4111-1111-1111-1234").replace("-", "")


def test_a_spaced_date_is_not_swept_up_as_an_identifier():
    words = _spaced_words(["15", "03", "2024"])
    result = sanitize.redact_line(words, [], False, False, sanitize.Stats())
    assert [w.text for w in result] == ["15", "03", "2024"]


def test_amounts_in_adjacent_columns_are_not_joined_into_an_identifier():
    """Two figures in neighbouring columns are far apart and carry decimals.
    Either property alone should keep them out of a digit run."""
    words = [
        sanitize.Word(text="120.00", x0=360, x1=386, top=0, bottom=9, size=9, bold=False),
        sanitize.Word(text="4,880.00", x0=510, x1=545, top=0, bottom=9, size=9, bold=False),
    ]
    result = sanitize.redact_line(words, [], False, False, sanitize.Stats())
    assert [w.text for w in result] == ["120.00", "4,880.00"]


def test_bare_integers_in_separate_columns_are_not_joined():
    """Pure digits, but a column apart - the gap is what says they are two
    numbers and not one."""
    words = [
        sanitize.Word(text="123456", x0=100, x1=130, top=0, bottom=9, size=9, bold=False),
        sanitize.Word(text="789012", x0=400, x1=430, top=0, bottom=9, size=9, bold=False),
    ]
    result = sanitize.redact_line(words, [], False, False, sanitize.Stats())
    # Each is still redacted on its own by the per-word rule, but separately.
    assert result[0].text != "123456"
    assert result[0].text == sanitize._pseudonym_digits("123456")


def _spaced_words(tokens: list[str]) -> list[sanitize.Word]:
    """Words laid out the way a PDF prints one grouped number: one space apart."""
    words = []
    x = 100.0
    for token in tokens:
        width = len(token) * 5.0
        words.append(sanitize.Word(text=token, x0=x, x1=x + width, top=0, bottom=9, size=9, bold=False))
        x += width + 2.5
    return words


# --- literal matching, which is the contributor's only lever ---------------


@pytest.mark.parametrize(
    ("printed", "typed"),
    [
        (["Anne", "Marie"], "Anne-Marie"),
        (["Anne-Marie"], "Anne Marie"),
        (["JANE", "WONG"], "jane wong"),
        (["O'BRIEN,"], "o brien"),
        (["MEI", "LING", "WONG"], "Mei Ling Wong"),
    ],
)
def test_a_name_matches_however_the_statement_split_it(printed, typed):
    """A contributor types their name the way they know it. They cannot be
    expected to guess how the PDF broke it into words."""
    words = _spaced_words(printed)
    hits = sanitize._literal_matches(words, [typed])
    assert hits == set(range(len(printed))), f"{typed!r} did not match {printed!r}"


@pytest.mark.parametrize("word", ["STANDARD", "INSTANT", "TANGERINE", "SUSTAIN"])
def test_a_short_name_does_not_strike_words_that_merely_contain_it(word):
    """Over-redaction is not free: what survives is the reason to share it."""
    words = _spaced_words([word])
    assert sanitize._literal_matches(words, ["TAN"]) == set()
