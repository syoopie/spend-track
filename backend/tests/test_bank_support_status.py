"""What the app claims about each bank has to match what its parser can do.

The dashboard's first-run copy, the Settings → Region card and the user
guide all say some banks parse and others are only recognized. Those claims
are generated from `BankParser.parsing_implemented` rather than typed out,
so these tests guard the flag itself: a stub that quietly starts claiming to
be implemented (or a finished parser still marked as a stub) would make
every one of those strings wrong at once.

Runs on any clone - the fixtures here are generated, not real statements.
"""

import io

import pdfplumber
import pytest
from reportlab.pdfgen import canvas

from app.localization import ACTIVE_COUNTRY
from app.parsing.base import UnparseableStatementError
from app.parsing.registry import detect_and_parse


def _pdf_with_text(*lines: str) -> bytes:
    """A one-page PDF carrying just enough text for a parser's detect()."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for i, line in enumerate(lines):
        c.drawString(72, 750 - i * 16, line)
    c.save()
    return buf.getvalue()


def _parse_bytes(data: bytes):
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return detect_and_parse(pdf.pages)


def test_only_uob_is_marked_implemented():
    implemented = [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers if p.parsing_implemented]
    detected_only = [p.bank_name for p in ACTIVE_COUNTRY.bank_parsers if not p.parsing_implemented]
    assert implemented == ["UOB"]
    assert detected_only == ["DBS", "OCBC"]


@pytest.mark.parametrize(
    ("bank", "anchor"),
    [("DBS", "DBS Bank"), ("DBS", "POSB"), ("OCBC", "OCBC Bank")],
)
def test_unimplemented_bank_is_detected_and_named_in_the_error(bank, anchor):
    # The precise "detected, but not supported yet" message is the whole
    # reason these stubs exist - without it the upload would come back as a
    # generic unrecognized format, which is what the UI promises it won't do.
    with pytest.raises(UnparseableStatementError) as excinfo:
        _parse_bytes(_pdf_with_text(f"{anchor} Statement of Account", "01 Jan  SOMETHING  12.34"))
    message = str(excinfo.value)
    assert bank in message
    assert "not yet implemented" in message


def test_unrecognized_pdf_error_names_only_banks_that_parse():
    with pytest.raises(UnparseableStatementError) as excinfo:
        _parse_bytes(_pdf_with_text("Some Other Bank Pte Ltd", "Statement"))
    message = str(excinfo.value)
    assert "UOB" in message
    # Naming a stub here would tell the user to try a bank that can't be read.
    assert "DBS" not in message
    assert "OCBC" not in message
