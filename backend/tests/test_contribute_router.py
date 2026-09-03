"""Tests for POST /api/contribute/sanitize.

The endpoint's job is not "return a smaller PDF" - it is to be honest about
what it produced, to someone who cannot open the file and check. So most of
what is pinned here is the shape of the answer rather than the redaction rules
themselves, which `test_sanitize_statement.py` already covers against the
bytes of the output.

Three of these exist because the honest answer and the convenient one differ.
A scanned statement sanitizes to a blank page that passes every check, and the
file is withheld rather than handed over looking successful. A file that fails
verification is handed over *with* its problems, because refusing outright
leaves a contributor with nothing to act on. And the chip list is allowed to be
incomplete - it structurally cannot contain an amount - so nothing may imply
that reading it is sufficient.
"""

import base64
import inspect
import io
import re
import sys
from pathlib import Path

import pdfplumber
import pypdf
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

import sanitize_statement
from app.parsing.registry import detect_and_parse

# Anchored on this file, not the working directory: these fixtures are
# committed, so unlike the optional `PDF Examples/` folder there is nothing to
# skip over and no reason to make the tests care where pytest was invoked from.
FIXTURES = Path(__file__).resolve().parents[2] / "PDF Examples (Sanitized)"
UOB_SAMPLE = FIXTURES / "UOB" / "Account Statements" / "SampleAccountStatement_Feb2024.pdf"
DBS_SAMPLE = FIXTURES / "DBS" / "Account Statements" / "SampleConsolidatedStatement_Dec2023.pdf"

ENDPOINT = "/api/contribute/sanitize"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SG_TRACKER_DB_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def _post(client, data: bytes, *, filename="statement.pdf", **fields):
    # httpx repeats a form field for each item of a list value, which is how
    # `redact` and `keep` reach the endpoint as the repeated fields it declares.
    form = {"bank": "UOB", **fields}
    return client.post(ENDPOINT, files={"file": (filename, io.BytesIO(data), "application/pdf")}, data=form)


def _decoded(body: dict) -> bytes:
    assert body["pdf_base64"] is not None, body["refusal_reason"]
    return base64.b64decode(body["pdf_base64"])


def _text_of(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _image_only_pdf() -> bytes:
    """A scan or a photo: shapes on the page, not one extractable word."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.rect(72, 500, 400, 200, fill=1)
    c.rect(72, 300, 400, 120, fill=1)
    c.showPage()
    c.save()
    return buf.getvalue()


def _trivial_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path))
    c.setFont("Helvetica", 9)
    c.drawString(36, 800, "BALANCE B/F 1,234.56")
    c.save()


def _encrypt(data: bytes, password: str) -> bytes:
    reader = pypdf.PdfReader(io.BytesIO(data))
    writer = pypdf.PdfWriter()
    for p in reader.pages:
        writer.add_page(p)
    writer.encrypt(user_password=password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_a_sanitized_fixture_round_trips_through_the_endpoint(client):
    """The whole premise: sanitizing costs a parser nothing. If the returned
    bytes read as a different statement than the input, the sample is useless
    however private it is."""
    resp = _post(client, UOB_SAMPLE.read_bytes())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["problems"] == []
    assert body["parse_status"] == "parsed"
    assert body["detected_bank"] == "UOB"

    with pdfplumber.open(UOB_SAMPLE) as pdf:
        before = detect_and_parse(pdf.pages)
    with pdfplumber.open(io.BytesIO(_decoded(body))) as pdf:
        after = detect_and_parse(pdf.pages)

    assert len(after.accounts) == len(before.accounts)
    for original, rebuilt in zip(before.accounts, after.accounts):
        assert [t.transaction_date for t in rebuilt.transactions] == [t.transaction_date for t in original.transactions]
        assert [t.amount for t in rebuilt.transactions] == [t.amount for t in original.transactions]


def test_a_scanned_statement_is_refused_rather_than_returned_blank(client):
    """A PDF with no text has no survivors, so verification passes vacuously
    and the output is a blank page. Handed over, that reads as "it removed
    everything, working correctly" to exactly the person this feature is for."""
    resp = _post(client, _image_only_pdf())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["word_count"] == 0
    assert body["pdf_base64"] is None
    assert body["refusal_reason"] == "no_text"
    assert body["problems"] == [], "nothing leaked - it is the wrong kind of file, not a failed check"


def test_removing_a_word_drops_it_from_the_list_and_the_output(client):
    """The core interaction: a word shows up in the chip list, the contributor
    strikes it out, and it is gone from both the list and the file.

    "Multiplier" is the case that motivates the chips at all - a word the
    vocabulary would otherwise preserve, which for someone called May or a
    merchant called Trust is their own name. It reaches the list here via
    `keep`, since the committed fixture is itself already sanitized."""
    data = DBS_SAMPLE.read_bytes()
    body = _post(client, data, bank="DBS", keep=["Multiplier"]).json()
    assert "Multiplier" in body["kept_words"]
    assert "Multiplier" in _text_of(_decoded(body))

    after = _post(client, data, bank="DBS", keep=["Multiplier"], redact=["Multiplier"]).json()
    assert "Multiplier" not in after["kept_words"]
    assert "Multiplier" not in _text_of(_decoded(after))


def test_a_file_that_fails_verification_is_still_returned_with_its_problems(client, monkeypatch):
    """Warn loudly, still allow the download. Refusing outright leaves the
    contributor with nothing to look at and no way to tell a real leak from a
    vocabulary gap - and the CLI's own refusal still writes its file for the
    same reason. Fail-open is this router's policy, so pin it here."""
    monkeypatch.setattr("app.sanitize.verify", lambda *a, **k: ["boom"])
    body = _post(client, UOB_SAMPLE.read_bytes()).json()
    assert body["problems"] == ["boom"]
    assert body["pdf_base64"] is not None


def test_the_cli_still_writes_the_file_it_refuses(tmp_path):
    """The router's fail-open policy lives in the router. If it ever migrates
    into `sanitize()`, the CLI stops being able to show a maintainer what
    leaked - so check the CLI's half of the same decision separately."""
    source = tmp_path / "JaneWong-Jan2024.pdf"
    _trivial_pdf(source)
    assert sanitize_statement.main([str(source), "--redact", "Jane Wong"]) == 1
    assert (tmp_path / "JaneWong-Jan2024.sanitized.pdf").is_file()


def test_nothing_from_the_uploaded_filename_reaches_the_response(client):
    """"JaneWong-Jan2024.pdf" identifies its owner as well as its contents do.
    Asserted over the whole body, not just `suggested_filename`, so an error
    message echoing the upload the way statements.py does fails this too."""
    resp = _post(
        client,
        UOB_SAMPLE.read_bytes(),
        filename="JaneWong-Jan2024.pdf",
        bank="UOB",
        redact=["Jane Wong"],
    )
    assert resp.status_code == 200, resp.text
    assert "jane" not in resp.text.lower()


def test_the_output_carries_no_timestamp_or_timezone(client):
    """Every sanitized sample this project shipped carried the author's local
    clock and timezone, `+08'00'` included - it places the contributor in
    Singapore and times the run against whenever they posted the issue.

    reportlab's invariant mode does not remove the date fields, it pins them to
    a fixed epoch, so the check is that no stamp carries a real time and that
    the same input renders to the same bytes."""
    data = UOB_SAMPLE.read_bytes()
    first = _decoded(_post(client, data).json())
    second = _decoded(_post(client, data).json())
    assert first == second

    stamps = set(re.findall(rb"/(?:Creation|Mod)Date\s*\((D:[^)]*)\)", first))
    assert stamps, "expected reportlab to write the date fields it pins"
    assert stamps == {b"D:20000101000000+00'00'"}


def test_an_encrypted_statement_uses_the_upload_flows_error_codes(client):
    """The same codes as /api/statements/upload, so the frontend's existing
    password prompt works here with no second branch to keep in step."""
    locked = _encrypt(UOB_SAMPLE.read_bytes(), "hunter2")

    resp = _post(client, locked)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "ENCRYPTED_PDF_PASSWORD_REQUIRED"

    resp = _post(client, locked, password="wrong")
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INCORRECT_PDF_PASSWORD"

    assert _post(client, locked, password="hunter2").status_code == 200


def test_the_chip_list_omits_amounts_and_short_numbers(client):
    """`kept_words` filters on isalpha, so it structurally cannot list an
    amount, a date, a house number or a #12 unit - all of which survive. Pinned
    so that nobody later writes "review this list and you're safe" over it."""
    body = _post(client, UOB_SAMPLE.read_bytes()).json()
    text = _text_of(_decoded(body))
    assert "5,000.00" in text and "7,843.45" in text
    for word in body["kept_words"]:
        assert any(c.isalpha() for c in word), f"{word!r} has no letter in it and should not be in the chip list"


def test_no_system_exit_can_escape_the_sanitize_module():
    """SystemExit is a BaseException. Raised in the anyio worker thread this
    endpoint runs in, it walks past Starlette's exception middleware and out of
    the process. Structural, because it is not reachable through the router."""
    import app.sanitize

    assert "SystemExit" not in inspect.getsource(app.sanitize)


def test_the_sanitizer_is_imported_from_main():
    """PyInstaller bundles what static analysis can see imported. A lazy
    import inside the handler would leave the packaged desktop build without
    reportlab or this module, and only fail once a user clicked the button."""
    import app.main  # noqa: F401

    assert "app.sanitize" in sys.modules


def test_the_endpoint_runs_off_the_event_loop():
    """pdfplumber and reportlab are CPU work with no await in them. Declared
    `async def`, they would block every other request for the length of a
    multi-page statement."""
    from app.routers import contribute

    assert not inspect.iscoroutinefunction(contribute.sanitize_statement)
