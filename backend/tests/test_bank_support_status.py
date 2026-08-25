"""What the app claims about each bank has to match what its parser can do.

The dashboard's first-run copy, the Settings → Region card and the user guide
all say which banks parse and which are only recognized. Those claims are
generated from `BankParser.parsing_implemented` rather than typed out, so
these tests guard the flag itself: a parser that quietly stopped claiming to
be implemented (or a stub claiming it is) would make every one of those
strings wrong at once.

All three Singapore banks parse now, so no *real* parser exercises the
detected-but-unimplemented path any more. That path is still live - it is what
a newly-stubbed bank gets on the day someone adds one - so it is tested here
against a stub defined for the purpose rather than deleted along with the last
real stub that used it.

Runs on any clone - the fixtures here are generated, not real statements.
"""

import io

import pdfplumber
import pytest
from reportlab.pdfgen import canvas

from app.localization import ACTIVE_COUNTRY
from app.parsing.base import BankParser, ParsedStatement, UnparseableStatementError
from app.parsing.registry import detect_and_parse


def _pdf_with_text(*lines: str) -> bytes:
    """A one-page PDF carrying just enough text for a parser's detect()."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(lines):
        c.drawString(72, 750 - i * 16, line)
    c.save()
    return buf.getvalue()


def _parse_bytes(data: bytes, parsers=None):
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return detect_and_parse(pdf.pages, parsers=parsers)


class _StubBank(BankParser):
    """A bank the app recognizes but cannot yet read - see parsing/base.py."""

    bank_name = "STUBBANK"
    parsing_implemented = False

    def detect(self, pages: list) -> bool:
        return "StubBank" in (pages[0].extract_text() or "")

    def parse(self, pages: list) -> ParsedStatement:
        raise UnparseableStatementError(
            "STUBBANK statement detected, but STUBBANK parsing is not yet implemented "
            "(no sample statements were available to build against)."
        )


def test_every_registered_singapore_bank_parses():
    implemented = [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers if p.parsing_implemented]
    detected_only = [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers if not p.parsing_implemented]
    assert implemented == ["UOB", "DBS", "OCBC"]
    assert detected_only == []


def test_unimplemented_bank_is_detected_and_named_in_the_error():
    # The precise "detected, but not supported yet" message is the whole reason
    # a stub is worth registering at all - without it the upload would come
    # back as a generic unrecognized format, which is what the UI promises it
    # won't do.
    with pytest.raises(UnparseableStatementError) as excinfo:
        _parse_bytes(
            _pdf_with_text("StubBank Statement of Account", "01 Jan  SOMETHING  12.34"),
            parsers=[_StubBank()],
        )
    message = str(excinfo.value)
    assert "STUBBANK" in message
    assert "not yet implemented" in message


def test_unrecognized_pdf_error_names_only_banks_that_parse():
    with pytest.raises(UnparseableStatementError) as excinfo:
        _parse_bytes(_pdf_with_text("Some Other Bank Pte Ltd", "Statement"), parsers=[*ACTIVE_COUNTRY.bank_parsers, _StubBank()])
    message = str(excinfo.value)
    for bank in ("UOB", "DBS", "OCBC"):
        assert bank in message
    # Naming a stub here would tell the user to try a bank that can't be read.
    assert "STUBBANK" not in message
