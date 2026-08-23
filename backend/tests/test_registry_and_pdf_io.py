import glob
import io

import pypdf
import pytest

from app.parsing.base import UnparseableStatementError
from app.parsing.pdf_io import EncryptedPdfError, IncorrectPasswordError, open_pdf
from app.parsing.registry import detect_and_parse

# PDF Examples/ is an optional, gitignored local folder for testing against
# your own real statements (see test_uob_account_parser.py) - discovered by
# glob rather than a hardcoded filename so no real statement's filename ever
# ends up in tracked source, and skipped entirely when absent (a fresh clone
# has none) rather than failing.
_ACCOUNT_SAMPLES = sorted(glob.glob("../PDF Examples/UOB/Account Statements/*.pdf"))
_CARD_SAMPLES = sorted(glob.glob("../PDF Examples/UOB/Card Statements/*.pdf"))
ACCOUNT_SAMPLE = _ACCOUNT_SAMPLES[0] if _ACCOUNT_SAMPLES else None
CARD_SAMPLE = _CARD_SAMPLES[0] if _CARD_SAMPLES else None

pytestmark = pytest.mark.skipif(
    ACCOUNT_SAMPLE is None or CARD_SAMPLE is None,
    reason="No real UOB statements found locally (optional, gitignored PDF Examples/ folder)",
)


def _encrypt(data: bytes, password: str) -> bytes:
    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt(user_password=password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_registry_dispatches_uob_account_statement():
    with open(ACCOUNT_SAMPLE, "rb") as f:
        pdf = open_pdf(f.read())
    result = detect_and_parse(pdf.pages)
    pdf.close()
    assert result.bank_name == "UOB"
    assert result.accounts[0].account_type == "One Account"


def test_registry_dispatches_uob_card_statement():
    with open(CARD_SAMPLE, "rb") as f:
        pdf = open_pdf(f.read())
    result = detect_and_parse(pdf.pages)
    pdf.close()
    assert result.bank_name == "UOB"
    assert result.accounts[0].account_type == "UOB ONE CARD"


def test_registry_raises_for_unrecognized_pdf():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    pdf = open_pdf(buf.getvalue())
    with pytest.raises(UnparseableStatementError):
        detect_and_parse(pdf.pages)
    pdf.close()


def test_encrypted_pdf_without_password_raises():
    with open(ACCOUNT_SAMPLE, "rb") as f:
        enc = _encrypt(f.read(), "secret123")
    with pytest.raises(EncryptedPdfError):
        open_pdf(enc)


def test_encrypted_pdf_with_wrong_password_raises():
    with open(ACCOUNT_SAMPLE, "rb") as f:
        enc = _encrypt(f.read(), "secret123")
    with pytest.raises(IncorrectPasswordError):
        open_pdf(enc, password="wrong")


def test_encrypted_pdf_with_correct_password_decrypts():
    with open(ACCOUNT_SAMPLE, "rb") as f:
        enc = _encrypt(f.read(), "secret123")
    pdf = open_pdf(enc, password="secret123")
    result = detect_and_parse(pdf.pages)
    pdf.close()
    assert len(result.accounts[0].transactions) == 39
